#!/usr/bin/env python3
"""
GeoVigilant Argus — Hugging Face Dataset Index Synchronizer
Downloads essential lightweight index files (~250 MB) from the Hugging Face
dataset repository (YTxFSGAMERz/ARGUS_DATASET) during container/cloud build,
enabling full spatial & perceptual search without storing 33.5 GB of images on disk.
"""

import os
import sys
import shutil
import time

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("[HF-SYNC] Warning: huggingface_hub is not installed. Skipping index sync.")
    sys.exit(0)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HF_REPO = os.environ.get("ARGUS_HF_DATASET", "YTxFSGAMERz/ARGUS_DATASET")

# Essential files to synchronize for the API to function without raw image storage
SYNC_TARGETS = [
    ("ARGUS_DATASET/indexes/state_tracker.db", os.path.join(BASE_DIR, "ARGUS_DATASET", "indexes", "state_tracker.db")),
    ("ARGUS_DATASET/indexes/phash_bktree.index", os.path.join(BASE_DIR, "ARGUS_DATASET", "indexes", "phash_bktree.index")),
    ("ARGUS_DATASET/places/places.csv", os.path.join(BASE_DIR, "ARGUS_DATASET", "places", "places.csv")),
    ("data/streetscapes/coords.csv", os.path.join(BASE_DIR, "data", "streetscapes", "coords.csv")),
]

def sync():
    print(f"============================================================")
    print(f"[HF-SYNC] Synchronizing dataset indices from {HF_REPO}...")
    print(f"============================================================")
    t0 = time.time()
    synced_count = 0

    for remote_path, local_dest in SYNC_TARGETS:
        if os.path.exists(local_dest) and os.path.getsize(local_dest) > 0:
            print(f"[HF-SYNC] [OK] Already present: {os.path.relpath(local_dest, BASE_DIR)} ({os.path.getsize(local_dest):,} bytes)")
            continue

        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        print(f"[HF-SYNC] Downloading {remote_path}...")
        try:
            downloaded = hf_hub_download(
                repo_id=HF_REPO,
                filename=remote_path,
                repo_type="dataset",
            )
            shutil.copy2(downloaded, local_dest)
            size_mb = os.path.getsize(local_dest) / (1024 * 1024)
            print(f"[HF-SYNC] [DOWNLOADED] -> {os.path.relpath(local_dest, BASE_DIR)} ({size_mb:.2f} MB)")
            synced_count += 1
        except Exception as e:
            print(f"[HF-SYNC] [WARNING] Could not download {remote_path}: {e}")

    elapsed = time.time() - t0
    print(f"[HF-SYNC] Sync complete: {synced_count} files downloaded in {elapsed:.2f}s")
    print(f"============================================================")

if __name__ == "__main__":
    sync()
