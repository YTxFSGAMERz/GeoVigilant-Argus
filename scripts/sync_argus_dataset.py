"""
ARGUS DATASET — Hugging Face Public Dataset Synchronizer.
Pushes updated metadata, indexes, reports, and geodata to the public repository:
https://huggingface.co/datasets/YTxFSGAMERz/ARGUS_DATASET
"""

import os
import sys
import time
import socket
import argparse

# Force IPv4 socket resolution to prevent Windows IPv6 TCP connection drops
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import HfApi, CommitOperationAdd

DATASET_REPO_ID = "YTxFSGAMERz/ARGUS_DATASET"
REPO_TYPE = "dataset"
ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
ARGUS_DIR = os.path.join(ROOT_DIR, "ARGUS_DATASET")

def main():
    parser = argparse.ArgumentParser(description="Sync ARGUS_DATASET to public Hugging Face repository.")
    parser.add_argument("--include-indexes", action="store_true", help="Include 230MB SQLite DB and pHash index")
    args = parser.parse_args()

    api = HfApi()
    user = api.whoami()
    print("=" * 80)
    print("  🚀 ARGUS DATASET — Hugging Face Public Dataset Synchronizer")
    print(f"  Target Repository: https://huggingface.co/datasets/{DATASET_REPO_ID} (Public)")
    print(f"  Authenticated As:  {user.get('name')}")
    print("=" * 80)

    # Critical metadata and reporting files to keep in sync
    sync_files = [
        ("README.md", os.path.join(ARGUS_DIR, "README.md")),
        ("ARGUS_DATASET/README.md", os.path.join(ARGUS_DIR, "README.md")),
        ("ARGUS_DATASET/places/places.csv", os.path.join(ARGUS_DIR, "places", "places.csv")),
        ("ARGUS_DATASET/places/places.jsonl", os.path.join(ARGUS_DIR, "places", "places.jsonl")),
        ("ARGUS_DATASET/places/coverage/category_coverage.json", os.path.join(ARGUS_DIR, "places", "coverage", "category_coverage.json")),
        ("ARGUS_DATASET/places/coverage/country_coverage.json", os.path.join(ARGUS_DIR, "places", "coverage", "country_coverage.json")),
        ("ARGUS_DATASET/metadata/images.csv", os.path.join(ARGUS_DIR, "metadata", "images.csv")),
        ("ARGUS_DATASET/metadata/images.jsonl", os.path.join(ARGUS_DIR, "metadata", "images.jsonl")),
        ("ARGUS_DATASET/metadata/licenses.csv", os.path.join(ARGUS_DIR, "metadata", "licenses.csv")),
        ("ARGUS_DATASET/metadata/sources.csv", os.path.join(ARGUS_DIR, "metadata", "sources.csv")),
        ("ARGUS_DATASET/reports/final_report.md", os.path.join(ARGUS_DIR, "reports", "final_report.md")),
        ("ARGUS_DATASET/reports/license_audit.json", os.path.join(ARGUS_DIR, "reports", "license_audit.json")),
    ]

    if args.include_indexes:
        sync_files.extend([
            ("ARGUS_DATASET/indexes/state_tracker.db", os.path.join(ARGUS_DIR, "indexes", "state_tracker.db")),
            ("ARGUS_DATASET/indexes/phash_bktree.index", os.path.join(ARGUS_DIR, "indexes", "phash_bktree.index")),
        ])

    operations = []
    for rel_path, local_path in sync_files:
        if os.path.exists(local_path):
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"  [+] Queueing: {rel_path} ({size_mb:.2f} MB)")
            operations.append(CommitOperationAdd(path_in_repo=rel_path, path_or_fileobj=local_path))
        else:
            print(f"  [!] Missing locally: {local_path}")

    if not operations:
        print("[!] No files to sync.")
        return

    print(f"\n[*] Committing {len(operations)} files to {DATASET_REPO_ID}...")
    t0 = time.time()
    commit = api.create_commit(
        repo_id=DATASET_REPO_ID,
        repo_type=REPO_TYPE,
        operations=operations,
        commit_message="Update ARGUS_DATASET metadata, places, and documentation"
    )
    t1 = time.time()
    print(f"  ✅ Sync complete in {t1 - t0:.2f}s!")
    print(f"  🔗 Commit: {commit.commit_url}")

if __name__ == "__main__":
    main()
