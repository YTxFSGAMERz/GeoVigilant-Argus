# 🔐 Security Policy
```
================================================================================
  [ ZERO-TRUST SECURITY POLICY & VULNERABILITY DISCLOSURE ]
================================================================================
```

This security policy outlines the zero-trust principles, cryptographic validation, and vulnerability reporting procedures governing the **GeoVigilant Argus Eye** platform.

![GeoVigilant Zero-Trust Architecture](screenshots/portfolio_landing.png)

---

## 🛡️ Supported Versions

Security updates are actively maintained for the current release stream on the `main` branch:

| Version | Supported | Security Maintenance Level |
| :--- | :--- | :--- |
| **v1.1.x / `main`** | ✅ Yes | Active patches, daily dependency scans, and vulnerability audits |
| `< v1.0.0` | ❌ No | Deprecated legacy releases |

---

## 🔒 Security Architecture & Defensive Mechanisms

### 1. Zero-Trust Telemetry Ingestion (Ed25519 & CRC-16)
Argus IoT ground mesh nodes sign all outbound telemetry packets using **Ed25519 digital signatures**. The server verifies:
* **Nonce Validation**: Prevents packet replay attacks.
* **Timestamp Windowing**: Packets older than 120 seconds are discarded to prevent stale spoofing.
* **CRC-16 Checksums**: Verifies binary packet integrity over unreliable RF channels.

### 2. Sandboxed Tor Proxy Routing
Dark web `.onion` queries are routed through an isolated SOCKS5 proxy running on `127.0.0.1:9050` or `127.0.0.1:9150`. The proxy runs without external clearnet packet leakage and isolates the operator's physical IP address.

### 3. Serverless Input Sanitization
All query parameters on public endpoints (`/api/tools/web_scan`, `/api/geovigilantai/chat`, `/api/flights`) are strictly validated against regex patterns to eliminate Server-Side Request Forgery (SSRF) and command injection risks.

---

## 🚨 Reporting a Vulnerability

If you identify a security vulnerability or credential leak, please report it responsibly:

> [!CAUTION]
> Do **NOT** disclose vulnerabilities publicly in GitHub Issues, pull requests, or community chat channels.

### Vulnerability Disclosure Channel
* **GitHub Security Advisory**: Submit a private advisory via [GitHub Security](https://github.com/YTxFSGAMERz/GeoVigilant-Argus/security/advisories)
* **Maintainer Contact**: Contact **YTxFSGAMERz** directly via repository channels.

Please provide:
1. **Description**: Concise summary of the vulnerability.
2. **Steps to Reproduce**: Reproduction script, curl command, or request payload.
3. **Impact Assessment**: Potential severity, exploitability, and attack vector.
4. **Proposed Patch**: Code patch or mitigation strategy if available.

We commit to acknowledging reports within 48 hours and deploying patches to the `main` branch within 7 days.

```
================================================================================
  [ END OF SECURITY POLICY ] // [ GEOVIGILANT ARGUS EYE ]
================================================================================
```
