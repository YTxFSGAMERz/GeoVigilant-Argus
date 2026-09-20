import os
import sys
import time
import socket

# Force IPv4 socket resolution to prevent Windows IPv6 TCP connection drops
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import HfApi, CommitOperationDelete

REPO_ID = "YTxFSGAMERz/ARGUS_DATASET"
REPO_TYPE = "dataset"

print("=" * 80)
print(f"  🧹 Pruning Non-Dataset Web App & Code Files from {REPO_ID}")
print("=" * 80)

api = HfApi()

info = api.repo_info(repo_id=REPO_ID, repo_type=REPO_TYPE)
siblings = [s.rfilename for s in info.siblings]

delete_prefixes = [
    'static/', 'templates/', 'tor-expert-bundle-windows-i686-15.0.19/', 'src/', 'scripts/',
    'globe/', 'argus/', 'dist/', 'public/', 'docs/', 'api/', 'config/', 'test/',
    'screenshots/', 'images/', 'ARGUS_DATASET/logs/'
]

to_delete = []
for s in siblings:
    if any(s.startswith(p) for p in delete_prefixes):
        to_delete.append(s)
    elif '/' not in s and s not in ['.gitattributes', 'README.md']:
        to_delete.append(s)

print(f"[*] Found {len(to_delete)} non-dataset files to prune.")

if not to_delete:
    print("[*] No files to delete. Already clean!")
    sys.exit(0)

operations = [CommitOperationDelete(path_in_repo=f) for f in to_delete]

print(f"[*] Submitting deletion commit for {len(operations)} files...")
t0 = time.time()
commit = api.create_commit(
    repo_id=REPO_ID,
    repo_type=REPO_TYPE,
    operations=operations,
    commit_message="Purge web application code, server configs, and local logs from ARGUS_DATASET"
)
t1 = time.time()
print(f"✅ Successfully pruned {len(operations)} files in {t1 - t0:.2f}s!")
print(f"🔗 Commit: {commit.commit_url}")
