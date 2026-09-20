"""
SQLite-Backed State Tracking Machine for ARGUS GroundView.
"""

import os
import sqlite3
import json
import logging
import datetime
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

class StateTracker:
    def __init__(self, db_path: str = "ARGUS_DATASET/indexes/state_tracker.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS places (
                place_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                aliases TEXT,
                country TEXT NOT NULL,
                city TEXT,
                category TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                wikidata_id TEXT,
                osm_id TEXT,
                wikipedia_url TEXT,
                commons_url TEXT,
                status TEXT DEFAULT 'DISCOVERED',
                images_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                image_id TEXT PRIMARY KEY,
                place_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT,
                source_url TEXT,
                local_path TEXT,
                image_type TEXT,
                status TEXT DEFAULT 'DISCOVERED',
                sha256 TEXT,
                phash TEXT,
                heading REAL,
                captured_at TEXT,
                width INTEGER,
                height INTEGER,
                license TEXT,
                license_url TEXT,
                author TEXT,
                attribution TEXT,
                file_size_bytes INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (place_id) REFERENCES places(place_id)
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS probe_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT NOT NULL,
                source TEXT NOT NULL,
                radius_m INTEGER,
                images_found INTEGER,
                timestamp TEXT
            )
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_status ON places(status);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_country ON places(country);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_place ON assets(place_id);
            """)
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);
            """)
            conn.commit()

    def upsert_place(self, place: Dict[str, Any]) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        aliases_json = json.dumps(place.get("aliases", []), ensure_ascii=False) if isinstance(place.get("aliases"), list) else place.get("aliases", "[]")
        
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO places (
                place_id, name, aliases, country, city, category,
                latitude, longitude, wikidata_id, osm_id, wikipedia_url, commons_url,
                status, images_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(place_id) DO UPDATE SET
                name = excluded.name,
                aliases = excluded.aliases,
                country = excluded.country,
                city = excluded.city,
                category = excluded.category,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                wikidata_id = COALESCE(places.wikidata_id, excluded.wikidata_id),
                osm_id = COALESCE(places.osm_id, excluded.osm_id),
                wikipedia_url = COALESCE(places.wikipedia_url, excluded.wikipedia_url),
                commons_url = COALESCE(places.commons_url, excluded.commons_url),
                updated_at = excluded.updated_at
            """, (
                place["place_id"], place["name"], aliases_json, place.get("country", "UNK"),
                place.get("city"), place.get("category", "landmark"),
                float(place["latitude"]), float(place["longitude"]),
                place.get("wikidata_id"), place.get("osm_id"),
                place.get("wikipedia_url"), place.get("commons_url"),
                place.get("status", "DISCOVERED"), place.get("images_count", 0),
                now, now
            ))
            conn.commit()
            return True

    def bulk_upsert_places(self, places: List[Dict[str, Any]]) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        records = []
        for p in places:
            aliases_json = json.dumps(p.get("aliases", []), ensure_ascii=False) if isinstance(p.get("aliases"), list) else p.get("aliases", "[]")
            records.append((
                p["place_id"], p["name"], aliases_json, p.get("country", "UNK"),
                p.get("city"), p.get("category", "landmark"),
                float(p["latitude"]), float(p["longitude"]),
                p.get("wikidata_id"), p.get("osm_id"),
                p.get("wikipedia_url"), p.get("commons_url"),
                p.get("status", "DISCOVERED"), p.get("images_count", 0),
                now, now
            ))
        
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.executemany("""
            INSERT INTO places (
                place_id, name, aliases, country, city, category,
                latitude, longitude, wikidata_id, osm_id, wikipedia_url, commons_url,
                status, images_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(place_id) DO UPDATE SET
                wikidata_id = COALESCE(places.wikidata_id, excluded.wikidata_id),
                osm_id = COALESCE(places.osm_id, excluded.osm_id),
                wikipedia_url = COALESCE(places.wikipedia_url, excluded.wikipedia_url),
                commons_url = COALESCE(places.commons_url, excluded.commons_url),
                updated_at = excluded.updated_at
            """, records)
            conn.commit()
            return len(records)

    def get_all_places(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM places ORDER BY country, name")
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("aliases"):
                    try:
                        d["aliases"] = json.loads(d["aliases"])
                    except Exception:
                        d["aliases"] = []
                results.append(d)
            return results

    def update_place_status(self, place_id: str, status: str, images_count: Optional[int] = None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.cursor()
            if images_count is not None:
                cur.execute("UPDATE places SET status = ?, images_count = ?, updated_at = ? WHERE place_id = ?",
                            (status, images_count, now, place_id))
            else:
                cur.execute("UPDATE places SET status = ?, updated_at = ? WHERE place_id = ?",
                            (status, now, place_id))
            conn.commit()

    def bulk_record_assets(self, assets: List[Dict[str, Any]]) -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        records = []
        place_ids = set()
        for asset in assets:
            place_ids.add(asset["place_id"])
            records.append((
                asset["image_id"], asset["place_id"], asset.get("source", "unknown"),
                asset.get("source_id"), asset.get("source_url"), asset.get("local_path"),
                asset.get("image_type", "landmark"), asset.get("status", "INGESTED"),
                asset.get("sha256"), asset.get("phash"), asset.get("heading"),
                asset.get("captured_at"), asset.get("width"), asset.get("height"),
                asset.get("license", "CC BY-SA 4.0"), asset.get("license_url"),
                asset.get("author", "Unknown"), asset.get("attribution", ""),
                asset.get("file_size_bytes", 0), now
            ))

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.executemany("""
            INSERT INTO assets (
                image_id, place_id, source, source_id, source_url, local_path,
                image_type, status, sha256, phash, heading, captured_at,
                width, height, license, license_url, author, attribution,
                file_size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(image_id) DO UPDATE SET
                status = excluded.status,
                sha256 = COALESCE(excluded.sha256, assets.sha256),
                phash = COALESCE(excluded.phash, assets.phash),
                local_path = COALESCE(excluded.local_path, assets.local_path),
                file_size_bytes = COALESCE(excluded.file_size_bytes, assets.file_size_bytes)
            """, records)

            for pid in place_ids:
                cur.execute("""
                UPDATE places SET images_count = (
                    SELECT COUNT(*) FROM assets WHERE place_id = ? AND status = 'INGESTED'
                ) WHERE place_id = ?
                """, (pid, pid))
            conn.commit()
        return len(records)

    def record_asset(self, asset: Dict[str, Any]) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO assets (
                image_id, place_id, source, source_id, source_url, local_path,
                image_type, status, sha256, phash, heading, captured_at,
                width, height, license, license_url, author, attribution,
                file_size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(image_id) DO UPDATE SET
                status = excluded.status,
                sha256 = COALESCE(excluded.sha256, assets.sha256),
                phash = COALESCE(excluded.phash, assets.phash),
                local_path = COALESCE(excluded.local_path, assets.local_path),
                file_size_bytes = COALESCE(excluded.file_size_bytes, assets.file_size_bytes)
            """, (
                asset["image_id"], asset["place_id"], asset.get("source", "unknown"),
                asset.get("source_id"), asset.get("source_url"), asset.get("local_path"),
                asset.get("image_type", "landmark"), asset.get("status", "DISCOVERED"),
                asset.get("sha256"), asset.get("phash"), asset.get("heading"),
                asset.get("captured_at"), asset.get("width"), asset.get("height"),
                asset.get("license", "CC BY-SA 4.0"), asset.get("license_url"),
                asset.get("author", "Unknown"), asset.get("attribution", ""),
                asset.get("file_size_bytes", 0), now
            ))
            cur.execute("""
            UPDATE places SET images_count = (
                SELECT COUNT(*) FROM assets WHERE place_id = ? AND status = 'INGESTED'
            ) WHERE place_id = ?
            """, (asset["place_id"], asset["place_id"]))
            conn.commit()
            return True

    def get_assets_for_place(self, place_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM assets WHERE place_id = ?", (place_id,))
            return [dict(r) for r in cur.fetchall()]

    def is_sha256_known(self, sha256: str) -> bool:
        if not sha256:
            return False
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM assets WHERE sha256 = ? LIMIT 1", (sha256,))
            return cur.fetchone() is not None

    def get_summary_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM places")
            total_places = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM places WHERE images_count > 0")
            places_with_images = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM assets WHERE status = 'INGESTED'")
            total_ingested_assets = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM assets WHERE status = 'INGESTED' AND image_type = 'landmark'")
            landmark_assets = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM assets WHERE status = 'INGESTED' AND image_type = 'street'")
            street_assets = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT country) FROM places")
            total_countries = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT city) FROM places WHERE city IS NOT NULL AND city != ''")
            total_cities = cur.fetchone()[0]
            
            cur.execute("SELECT SUM(file_size_bytes) FROM assets WHERE status = 'INGESTED'")
            total_bytes = cur.fetchone()[0] or 0
            
            return {
                "total_places": total_places,
                "places_with_images": places_with_images,
                "places_without_images": total_places - places_with_images,
                "total_ingested_assets": total_ingested_assets,
                "landmark_assets": landmark_assets,
                "street_assets": street_assets,
                "total_countries": total_countries,
                "total_cities": total_cities,
                "total_storage_mb": round(total_bytes / (1024 * 1024), 2),
                "total_storage_gb": round(total_bytes / (1024 ** 3), 4)
            }
