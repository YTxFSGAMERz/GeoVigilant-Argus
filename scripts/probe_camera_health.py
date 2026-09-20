"""
ARGUS DATASET — Surveillance Camera Stream Health & Live Verification Engine.

Probes camera live stream websites and RTSP/HTTP endpoints concurrently,
verifying network availability, response latency, and stream health.
Updates surveillance_cameras table in state_tracker.db with live telemetry.
"""

import os
import sys
import time
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ARGUS_DATASET", "indexes", "state_tracker.db")

HEADERS = {
    "User-Agent": "ARGUS-Geoint-StreamProber/2.0 (Security Telemetry Audit; Automated Grid Health Check)"
}


def ensure_health_columns(conn: sqlite3.Connection):
    """Adds stream_status, last_probed_at, latency_ms columns if missing."""
    c = conn.cursor()
    c.execute("PRAGMA table_info(surveillance_cameras)")
    existing_cols = set(row[1] for row in c.fetchall())

    if "stream_status" not in existing_cols:
        c.execute("ALTER TABLE surveillance_cameras ADD COLUMN stream_status TEXT DEFAULT 'UNPROBED'")
    if "last_probed_at" not in existing_cols:
        c.execute("ALTER TABLE surveillance_cameras ADD COLUMN last_probed_at INTEGER DEFAULT 0")
    if "latency_ms" not in existing_cols:
        c.execute("ALTER TABLE surveillance_cameras ADD COLUMN latency_ms REAL DEFAULT 0.0")

    conn.commit()


def probe_single_camera(cam_id: int, url: str) -> Tuple[int, str, float]:
    """Tests HTTP/HTTPS stream connectivity with low latency timeout."""
    if not url or not url.startswith("http"):
        return cam_id, "NO_URL", 0.0

    t0 = time.time()
    try:
        resp = requests.head(url, headers=HEADERS, timeout=2.0, allow_redirects=True)
        latency = round((time.time() - t0) * 1000, 2)
        if 200 <= resp.status_code < 400:
            return cam_id, "ONLINE", latency
        elif resp.status_code in (401, 403):
            return cam_id, "RESTRICTED", latency
        else:
            return cam_id, "OFFLINE", latency
    except requests.exceptions.Timeout:
        return cam_id, "TIMEOUT", 2000.0
    except requests.exceptions.RequestException:
        return cam_id, "OFFLINE", 0.0


def run_batch_probe(sample_limit: int = 50, max_workers: int = 16):
    print("================================================================")
    print("  ARGUS DATASET — SURVEILLANCE STREAM HEALTH PROBING ENGINE     ")
    print("================================================================")
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    ensure_health_columns(conn)

    c = conn.cursor()
    c.execute("""
        SELECT id, website FROM surveillance_cameras
        WHERE website IS NOT NULL AND website != '' AND stream_status = 'UNPROBED'
        LIMIT ?
    """, (sample_limit,))
    cams = c.fetchall()

    if not cams:
        c.execute("""
            SELECT id, website FROM surveillance_cameras
            WHERE website IS NOT NULL AND website != ''
            LIMIT ?
        """, (sample_limit,))
        cams = c.fetchall()

    print(f"Targeting batch of {len(cams)} camera endpoints with {max_workers} concurrent workers...")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(probe_single_camera, cid, url): cid for cid, url in cams}
        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception:
                pass

    # Update database
    now_ts = int(time.time())
    update_batch = [(status, latency, now_ts, cid) for cid, status, latency in results]
    c.executemany("""
        UPDATE surveillance_cameras
        SET stream_status = ?, latency_ms = ?, last_probed_at = ?
        WHERE id = ?
    """, update_batch)
    conn.commit()

    online_cnt = sum(1 for _, st, _ in results if st == "ONLINE")
    restricted_cnt = sum(1 for _, st, _ in results if st == "RESTRICTED")
    offline_cnt = sum(1 for _, st, _ in results if st in ("OFFLINE", "TIMEOUT"))

    print(f"\n✓ Probed {len(results)} cameras in {time.time() - t0:.2f}s:")
    print(f"  • ONLINE / STREAMING: {online_cnt}")
    print(f"  • RESTRICTED / AUTH:  {restricted_cnt}")
    print(f"  • OFFLINE / TIMEOUT:  {offline_cnt}")
    print("================================================================")
    conn.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_batch_probe(sample_limit=limit)
