"""
GeoVigilant Argus — Automated Private Vault Credentials Restorer.

Pulls the live .env credentials from the owner's private Hugging Face vault:
https://huggingface.co/datasets/YTxFSGAMERz/GeoVigilant-Argus (Private)

- If run by the owner (authenticated with HF token): Restores live .env automatically.
- If run by an external user (unauthenticated): Access is denied, and fallback .env.example is offered.
"""

import os
import sys
import socket
import shutil
import argparse

# Force IPv4 socket resolution on Windows to prevent TCP connection drops
_old_gai = socket.getaddrinfo
def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
    return _old_gai(host, port, family=socket.AF_INET, type=type, proto=proto, flags=flags)
socket.getaddrinfo = _ipv4_gai

os.environ["HF_HUB_DISABLE_XET"] = "1"

REPO_ID = "YTxFSGAMERz/GeoVigilant-Argus"
REPO_TYPE = "dataset"
ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
TARGET_ENV = os.path.join(ROOT_DIR, ".env")
EXAMPLE_ENV = os.path.join(ROOT_DIR, ".env.example")

def pull_env(force=False):
    if os.path.exists(TARGET_ENV) and os.path.getsize(TARGET_ENV) > 0 and not force:
        print("  [*] Local .env already exists. Use '--force' to overwrite from private vault.")
        return True

    print("=" * 75)
    print("  🔒 GeoVigilant Argus — Secure Credentials Vault Synchronization")
    print(f"  Target Vault: https://huggingface.co/datasets/{REPO_ID} (Private)")
    print("=" * 75)

    try:
        from huggingface_hub import hf_hub_download, HfApi
        api = HfApi()
        user_info = api.whoami()
        username = user_info.get("name", "Unknown")
        print(f"  [*] Authenticated as: {username}")

        print("  [*] Fetching encrypted .env payload from private vault...")
        downloaded_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=".env",
            repo_type=REPO_TYPE,
            force_download=True
        )

        shutil.copyfile(downloaded_path, TARGET_ENV)
        size_bytes = os.path.getsize(TARGET_ENV)
        print("  " + "-" * 71)
        print(f"  ✅ [SUCCESS] Restored .env from private vault ({size_bytes} bytes).")
        print("  🔒 Full credentials, API tokens, and session secrets are now active.")
        print("  " + "-" * 71)
        return True

    except Exception as e:
        err_msg = str(e)
        print("  " + "-" * 71)
        print("  ⚠️  [ACCESS RESTRICTED] Unable to download .env from private vault.")

        if "401" in err_msg or "403" in err_msg or "RepositoryNotFoundError" in err_msg or "Gated" in err_msg:
            print("  🔒 The credentials vault is STRICTLY PRIVATE to the project owner.")
            print("     Only authorized maintainers can pull live production keys.")
            print("     If you are the owner, run: 'hf auth login'")
        else:
            print(f"     Reason: {err_msg}")

        # Fallback to .env.example for external developers
        if not os.path.exists(TARGET_ENV) and os.path.exists(EXAMPLE_ENV):
            print("\n  💡 Initializing template .env from .env.example for local development...")
            shutil.copyfile(EXAMPLE_ENV, TARGET_ENV)
            print("  ⚠️  Please populate your local .env with your own API keys.")
        print("  " + "-" * 71)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore .env from private Hugging Face credentials vault.")
    parser.add_argument("--force", "-f", action="store_true", help="Force overwrite existing local .env")
    args = parser.parse_args()
    pull_env(force=args.force)
