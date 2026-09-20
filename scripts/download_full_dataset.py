"""
GeoVigilant Argus Eye — Full Dataset Downloader.
Downloads the complete ARGUS_DATASET (including 75,000+ surveillance images, ~36.9 GB)
from the public Hugging Face repository: https://huggingface.co/datasets/YTxFSGAMERz/ARGUS_DATASET
"""

import os
import sys
import socket
import argparse

# Force IPv4 socket resolution to prevent Windows IPv6 TCP connection drops
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

os.environ["HF_HUB_DISABLE_XET"] = "1"

ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATASET_REPO = "YTxFSGAMERz/ARGUS_DATASET"

def main():
    parser = argparse.ArgumentParser(description="Download ARGUS dataset files from public Hugging Face repository.")
    parser.add_argument("--all", action="store_true", help="Download entire dataset including 75,000+ images (~36.9 GB)")
    parser.add_argument("--indexes-only", action="store_true", help="Download only essential databases and indexes (~250 MB)")
    args = parser.parse_args()

    print("=" * 80)
    print("  🛰️ ARGUS DATASET — PUBLIC REPOSITORY DOWNLOADER")
    print(f"  Source: https://huggingface.co/datasets/{DATASET_REPO} (Public)")
    print(f"  Target: {os.path.join(ROOT_DIR, 'ARGUS_DATASET')}")
    print("=" * 80)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[!] Installing huggingface_hub...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
        from huggingface_hub import snapshot_download

    if args.indexes_only or not args.all:
        print("\n[*] Downloading core indexes and metadata (~250 MB)...")
        allow_patterns = [
            "ARGUS_DATASET/indexes/*",
            "ARGUS_DATASET/places/*",
            "ARGUS_DATASET/metadata/*",
            "ARGUS_DATASET/reports/*",
            "geodata/*"
        ]
        snapshot_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            local_dir=ROOT_DIR,
            allow_patterns=allow_patterns,
            resume_download=True
        )
        print("\n[+] Core dataset indexes and metadata downloaded successfully!")
        if not args.all:
            print("\n[i] Note: To download the full 36.9 GB image archive (75,000+ photos), run:")
            print("    python scripts/download_full_dataset.py --all")
    else:
        print("\n[*] Downloading FULL dataset including 75,000+ images (~36.9 GB)...")
        print("    This may take several minutes depending on your internet connection.")
        snapshot_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            local_dir=ROOT_DIR,
            resume_download=True
        )
        print("\n[+] Complete ARGUS dataset downloaded successfully!")

if __name__ == "__main__":
    main()
