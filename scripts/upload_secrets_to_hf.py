"""
GeoVigilant Argus — Automated Private Vault Credentials & Secrets Synchronizer

Tracks and synchronizes private configuration files, credentials, and Tor routing
assets from the local repository directly to the private Hugging Face vault:
https://huggingface.co/datasets/YTxFSGAMERz/GeoVigilant-Argus (Private)

Usage:
  python scripts/upload_secrets_to_hf.py
  python scripts/upload_secrets_to_hf.py --include-tor
  python scripts/upload_secrets_to_hf.py --message "Update API keys"
"""

import os
import sys
import time
import socket
import argparse
import hashlib

# Force IPv4 socket resolution on Windows to prevent TCP connection drops
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import HfApi, CommitOperationAdd

REPO_ID = "YTxFSGAMERz/GeoVigilant-Argus"
REPO_TYPE = "dataset"
ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Core private configuration and secret files
TRACKED_CORE_FILES = [
    ".env",
    ".env.example",
    "API Required.txt",
    "torrc",
]

# Tor bundle assets (configs, binaries, pluggable transports)
TRACKED_TOR_FILES = [
    "tor-expert-bundle-windows-i686-15.0.19/data/geoip",
    "tor-expert-bundle-windows-i686-15.0.19/data/geoip6",
    "tor-expert-bundle-windows-i686-15.0.19/data/torrc-defaults",
    "tor-expert-bundle-windows-i686-15.0.19/docs/conjure.txt",
    "tor-expert-bundle-windows-i686-15.0.19/docs/libevent.txt",
    "tor-expert-bundle-windows-i686-15.0.19/docs/lyrebird.txt",
    "tor-expert-bundle-windows-i686-15.0.19/docs/openssl.txt",
    "tor-expert-bundle-windows-i686-15.0.19/docs/tor.txt",
    "tor-expert-bundle-windows-i686-15.0.19/docs/zlib.txt",
    "tor-expert-bundle-windows-i686-15.0.19/tor/tor-gencert.exe",
    "tor-expert-bundle-windows-i686-15.0.19/tor/tor.exe",
    "tor-expert-bundle-windows-i686-15.0.19/tor/pluggable_transports/conjure-client.exe",
    "tor-expert-bundle-windows-i686-15.0.19/tor/pluggable_transports/lyrebird.exe",
    "tor-expert-bundle-windows-i686-15.0.19/tor/pluggable_transports/pt_config.json",
    "tor-expert-bundle-windows-i686-15.0.19/tor/pluggable_transports/README.CONJURE.md",
]

def get_file_hash(filepath):
    """Computes SHA256 of local file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def sync_secrets(commit_message=None, include_tor=True):
    print("=" * 78)
    print("  🔒 GeoVigilant Argus — Hugging Face Private Vault Synchronizer")
    print(f"  Target Vault: https://huggingface.co/datasets/{REPO_ID} (Private)")
    print("=" * 78)

    api = HfApi()

    try:
        user = api.whoami()
        username = user.get("name", "Unknown")
        print(f"  [*] Authenticated as: {username}")
        if username != "YTxFSGAMERz":
            print(f"  ⚠️  Warning: Authenticated user is '{username}', expected 'YTxFSGAMERz'.")
    except Exception as e:
        print(f"  ❌ Authentication error: {e}")
        print("     Run 'huggingface-cli login' or 'hf auth login' first.")
        sys.exit(1)

    files_to_track = list(TRACKED_CORE_FILES)
    if include_tor:
        files_to_track.extend(TRACKED_TOR_FILES)

    operations = []
    staged_summary = []

    print("\n  [*] Scanning local repository for tracked secrets & configuration files...")
    for rel_path in files_to_track:
        local_path = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
        if os.path.exists(local_path):
            size_bytes = os.path.getsize(local_path)
            operations.append(CommitOperationAdd(
                path_in_repo=rel_path,
                path_or_fileobj=local_path
            ))
            staged_summary.append((rel_path, size_bytes))
            print(f"   [+] STAGED: {rel_path:<45} ({size_bytes:>8} bytes)")
        else:
            print(f"   [-] SKIPPED (not found locally): {rel_path}")

    if not operations:
        print("\n  ⚠️  No tracked files found locally to upload.")
        return False

    if not commit_message:
        commit_message = f"Sync private configuration vault ({len(operations)} tracked files)"

    print("\n" + "-" * 78)
    print(f"  [*] Uploading {len(operations)} file(s) to {REPO_ID}...")
    print(f"  [*] Commit Message: \"{commit_message}\"")
    print("-" * 78)

    t0 = time.time()
    try:
        commit = api.create_commit(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            operations=operations,
            commit_message=commit_message
        )
        duration = round(time.time() - t0, 2)
        print("  " + "-" * 76)
        print(f"  ✅ [SUCCESS] Private vault synchronized in {duration}s!")
        print(f"  🔗 Commit URL: {commit.commit_url}")
        print("  " + "-" * 76)
        return True
    except Exception as e:
        print(f"  ❌ Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload private credentials & secrets to Hugging Face vault.")
    parser.add_argument("--message", "-m", type=str, default=None, help="Custom commit message")
    parser.add_argument("--no-tor", action="store_true", help="Exclude Tor bundle files (only upload .env and text credentials)")
    args = parser.parse_args()

    sync_secrets(commit_message=args.message, include_tor=not args.no_tor)
