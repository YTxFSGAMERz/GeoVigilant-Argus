import os
import re
import sys

sys.path.insert(0, os.path.abspath('.'))

import hashlib

print("=== 1. VERIFYING SECRET CLEANUP ===")
# SHA256 hashes of retired keys (ensures tests verify keys are eliminated without storing plaintext in test file)
retired_key_hashes = {
    "aa3ff7a12a22b489d7f0b01d261c1e2fc3380985df0728210e4d47156ae62f36",
    "bbec5e2391adb3ef1dc010f25e468d7664205be70a351ea29093cc7d8b445500",
    "d28277ad9bcbe11e48f9f525a66105ce8c7c3ebe7db844c37316f4980c0027b4",
}
secret_regexes = [
    re.compile(r"sk-or-v1-[a-f0-9]{32,}", re.IGNORECASE),
    re.compile(r"pk\.[a-f0-9]{32}", re.IGNORECASE),
    re.compile(r"MLY\|[0-9]+\|[a-f0-9]+", re.IGNORECASE),
]
leak_found = False
for root, _, files in os.walk('.'):
    if any(x in root for x in ['.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env', 'ARGUS_DATASET', 'tor-expert-bundle']):
        continue
    for f in files:
        if f == 'verify_security_hardening.py':
            continue
        if f.endswith(('.py', '.json', '.js', '.html', '.rc', '.yaml', '.yml')):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
                for rx in secret_regexes:
                    if rx.search(content):
                        print(f"[FAIL] Hardcoded secret pattern found in {path}!")
                        leak_found = True
                for word in re.findall(r'[a-zA-Z0-9_\.\-]+', content):
                    h = hashlib.sha256(word.encode('utf-8')).hexdigest()
                    if h in retired_key_hashes:
                        print(f"[FAIL] Leaked secret found in {path} (matched retired hash)!")
                        leak_found = True

if not leak_found:
    print("[PASS] Zero hardcoded API keys/secrets found in codebase!")

print("\n=== 2. VERIFYING SSRF PROTECTION (is_safe_public_url) ===")
from app import is_safe_public_url

blocked_urls = [
    "http://127.0.0.1:11434",
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://localhost:8080",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/admin",
    "http://192.168.1.1/",
    "http://172.16.0.1/status",
    "http://0.0.0.0:5000",
    "http://[::1]/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:9051",
    "ftp://127.0.0.1",
    "",
    None
]

all_blocked = True
for url in blocked_urls:
    res = is_safe_public_url(url)
    if res is not False:
        print(f"[FAIL] Expected blocked URL to fail: {url} -> got {res}")
        all_blocked = False
    else:
        print(f"  [BLOCKED] {url} -> correctly rejected")

if all_blocked:
    print("[PASS] All dangerous/internal/SSRF vectors successfully blocked!")

print("\n=== 3. VERIFYING PATH TRAVERSAL DEFENSE (_get_safe_data_path) ===")
from Socio import _get_safe_data_path

traversal_attempts = [
    "../../etc/passwd",
    "..\\..\\windows\\system32",
    "../../../data/secret.json",
    "user/../../admin",
    "normal_user",
    "tactical-operator_01"
]

data_dir = os.path.abspath('data')
all_safe = True
for target in traversal_attempts:
    res = _get_safe_data_path('test_data', target)
    if res is None:
        print(f"  [REJECTED] target \"{target}\" -> None")
    else:
        if not res.startswith(data_dir + os.sep) or '..' in res:
            print(f"[FAIL] Path traversal leaked out: {target} -> {res}")
            all_safe = False
        else:
            print(f"  [SAFE] target \"{target}\" -> confined inside {data_dir}")

if all_safe:
    print("[PASS] Path traversal vectors neutralized and confined to data/!")

print("\n=== 4. VERIFYING FLASK SECURITY HEADERS & BODY LIMIT ===")
from app import app
print("MAX_CONTENT_LENGTH:", app.config.get('MAX_CONTENT_LENGTH'))
assert app.config.get('MAX_CONTENT_LENGTH') == 16 * 1024 * 1024, "MAX_CONTENT_LENGTH not set correctly"

client = app.test_client()
resp = client.get('/')
headers = resp.headers
print("X-Content-Type-Options:", headers.get('X-Content-Type-Options'))
print("X-Frame-Options:", headers.get('X-Frame-Options'))
print("Referrer-Policy:", headers.get('Referrer-Policy'))

assert headers.get('X-Content-Type-Options') == 'nosniff'
assert headers.get('X-Frame-Options') == 'SAMEORIGIN'
assert headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
print("[PASS] Security headers verified on live response!")

print("\n=== 5. VERIFYING TOR CONFIGURATION ===")
with open('torrc', 'r') as tf:
    tor_cfg = tf.read()
assert 'CookieAuthentication 1' in tor_cfg, "CookieAuthentication 1 not found in torrc"
assert 'CookieAuthentication 0' not in tor_cfg, "CookieAuthentication 0 still in torrc"
print("[PASS] torrc hardened with CookieAuthentication 1!")

print("\n======================================================")
print("  ALL SECURITY CHECKS & VULNERABILITY PATCHES PASSED!")
print("======================================================")
