import os
import sys
import time
import socket

# ---------------------------------------------------------------------------
# Force IPv4 socket resolution to prevent Windows IPv6 TCP connection drops
# ---------------------------------------------------------------------------
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

# Disable XET middleware for direct reliable HTTPS upload on Windows
os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import HfApi, CommitOperationAdd

# NOTE: "YTxFSGAMERz/GeoVigilant-Argus" is the PRIVATE full repository backup.
# For syncing the PUBLIC dataset, use "scripts/sync_argus_dataset.py" which targets "YTxFSGAMERz/ARGUS_DATASET".
REPO_ID = "YTxFSGAMERz/GeoVigilant-Argus"
REPO_TYPE = "dataset"
ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

print("=" * 80)
print("  🔒 GeoVigilant Argus Eye — Hugging Face PRIVATE Repo Backup Synchronizer")
print(f"  Target Repository: https://huggingface.co/datasets/{REPO_ID} (Private Backup)")
print("=" * 80)

api = HfApi()

try:
    user = api.whoami()
    print(f"[*] Authenticated as: {user.get('name', 'Unknown')}")
except Exception as e:
    print(f"[!] Authentication error: {e}")
    sys.exit(1)

# 1. Documentation Markdown Files (13 files)
doc_files = [
    "README.md",
    "SYSTEM_SPEC.md",
    "OPERATOR_GUIDE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "docs/criminal_recon_manual.md",
    "docs/geosential_ai.md",
    "docs/geovigilant_ai.md",
    "docs/presentation_guide.md",
    "docs/search_options.md",
    "globe/README.md",
    "ARGUS_DATASET/reports/final_report.md"
]

# 2. Operational, launch, and configuration files
operational_files = [
    "start.bat",
    "start.sh",
    "stop.bat",
    "app.py",
    "requirements.txt",
    "package.json",
    "torrc",
    "vite.config.js",
    "streetscapes_service.py",
    "argus_unified_dataset_service.py",
    "scripts/sync_to_hf.py",
    "scripts/extract_streetscapes.py",
    "scripts/expand_landmarks.py",
    "scripts/index_vector_embeddings.py",
    "scripts/ingest_defense_infrastructure.py",
    "scripts/probe_camera_health.py",
    "scripts/unify_datasets.py",
    "scripts/verify_dataset_upgrade.py",
    "scripts/verify_unified_dataset.py",
    "scripts/verify_security_hardening.py",
]

# 3. Screenshot Images
screenshot_dir = os.path.join(ROOT_DIR, "screenshots")
screenshot_files = []
if os.path.exists(screenshot_dir):
    for fname in sorted(os.listdir(screenshot_dir)):
        if fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            screenshot_files.append(f"screenshots/{fname}")

def build_operations(file_list):
    ops = []
    for rel_path in file_list:
        full_path = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
        if os.path.exists(full_path):
            size_kb = os.path.getsize(full_path) / 1024.0
            ops.append((rel_path, full_path, size_kb))
        else:
            print(f"[!] Warning: File not found locally, skipping: {rel_path}")
    return ops

# Build ops for Docs & Scripts
docs_ops_data = build_operations(doc_files + operational_files)
screenshots_ops_data = build_operations(screenshot_files)

print(f"\n[*] Prepared {len(docs_ops_data)} documentation & script files to sync.")
print(f"[*] Prepared {len(screenshots_ops_data)} screenshot assets to sync.")

# Execute Commit 1: Documentation & Operational Scripts
print("\n" + "-" * 60)
print("  STEP 1: Uploading Documentation & Core Scripts")
print("-" * 60)
ops1 = [
    CommitOperationAdd(path_in_repo=rel_path, path_or_fileobj=full_path)
    for rel_path, full_path, _ in docs_ops_data
]

try:
    t0 = time.time()
    commit_1 = api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        operations=ops1,
        commit_message="Update documentation with zero-API quickstart, operator guides, and service scripts"
    )
    t1 = time.time()
    print(f"  ✅ Step 1 Success ({t1 - t0:.2f}s)")
    print(f"  🔗 Commit: {commit_1.commit_url}")
except Exception as e:
    print(f"  ❌ Step 1 failed: {e}")
    sys.exit(1)

# Execute Commit 2: High-Resolution Screenshots
print("\n" + "-" * 60)
print("  STEP 2: Uploading High-Resolution Screenshots & Assets")
print("-" * 60)
ops2 = [
    CommitOperationAdd(path_in_repo=rel_path, path_or_fileobj=full_path)
    for rel_path, full_path, _ in screenshots_ops_data
]

try:
    t0 = time.time()
    commit_2 = api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        operations=ops2,
        commit_message="Add high-resolution surveillance HUD, OSINT feeds, and map mode screenshots"
    )
    t1 = time.time()
    print(f"  ✅ Step 2 Success ({t1 - t0:.2f}s)")
    print(f"  🔗 Commit: {commit_2.commit_url}")
except Exception as e:
    print(f"  ❌ Step 2 failed: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("  🎉 ALL ASSETS & DOCUMENTATION SUCCESSFULLY SYNCED TO HUGGING FACE!")
print(f"  Dataset URL: https://huggingface.co/datasets/{REPO_ID}")
print("=" * 80)
