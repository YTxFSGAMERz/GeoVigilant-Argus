import * as ed from '@noble/ed25519';
import { sha256, sha512 } from '@noble/hashes/sha2.js';
import { bytesToHex } from '@noble/hashes/utils.js';
import { IntegrityStatus } from '../types/events.js';

if (ed.hashes) {
  ed.hashes.sha512 = sha512;
}

export class TelemetryIntegrityChecker {
  /**
   * @param {Object} keyRegistry - { getPublicKey: (nodeId) => Uint8Array | undefined }
   * @param {number} maxTimestampDriftMs
   */
  constructor(keyRegistry, maxTimestampDriftMs = 15000) {
    this.keyRegistry = keyRegistry;
    this.maxTimestampDriftMs = maxTimestampDriftMs;
    this.nonceCache = new Map();
    this.maxNonceEntries = 10000;
  }

  /**
   * Verified Execution Order:
   * 1. CRC Check (CRC_FAILURE)
   * 2. Known Node Lookup (UNKNOWN_NODE)
   * 3. Ed25519 Signature Verification (INVALID_SIGNATURE)
   * 4. Timestamp Window Check (STALE_TIMESTAMP)
   * 5. Nonce Replay Check (REPLAYED)
   * 6. Record Nonce in Bounded Cache
   * 7. Assign VERIFIED
   */
  verifyFrame(
    nodeId,
    canonicalPayloadBytes,
    signatureBytes,
    nonce,
    timestampMs,
    receivedAtMs,
    crcValid = true
  ) {
    const driftMs = Math.abs(receivedAtMs - timestampMs);

    // 1. Structural CRC Check
    if (!crcValid) {
      return {
        status: IntegrityStatus.CRC_FAILURE,
        signatureAlgorithm: 'ED25519',
        signatureValid: false,
        nonceSeen: false,
        timestampDriftMs: driftMs,
        crcValid: false,
      };
    }

    // 2. Known Node Lookup
    const pubKey = this.keyRegistry.getPublicKey(nodeId);
    if (!pubKey) {
      return {
        status: IntegrityStatus.UNKNOWN_NODE,
        signatureAlgorithm: 'ED25519',
        signatureValid: false,
        nonceSeen: false,
        timestampDriftMs: driftMs,
        crcValid: true,
      };
    }

    const keyId = bytesToHex(pubKey.slice(0, 4));

    // 3. Ed25519 Digital Signature Verification
    let isValidSig = false;
    try {
      isValidSig = ed.verify(signatureBytes, canonicalPayloadBytes, pubKey);
    } catch {
      isValidSig = false;
    }

    if (!isValidSig) {
      return {
        status: IntegrityStatus.INVALID_SIGNATURE,
        signatureAlgorithm: 'ED25519',
        signatureValid: false,
        nonceSeen: false,
        timestampDriftMs: driftMs,
        crcValid: true,
        signerKeyId: keyId,
      };
    }

    // 4. Timestamp Freshness Window
    if (driftMs > this.maxTimestampDriftMs) {
      return {
        status: IntegrityStatus.STALE_TIMESTAMP,
        signatureAlgorithm: 'ED25519',
        signatureValid: true,
        nonceSeen: false,
        timestampDriftMs: driftMs,
        crcValid: true,
        signerKeyId: keyId,
      };
    }

    // 5. Anti-Replay Detection
    const nonceKey = `${nodeId}:${nonce}`;
    if (this.nonceCache.has(nonceKey)) {
      return {
        status: IntegrityStatus.REPLAYED,
        signatureAlgorithm: 'ED25519',
        signatureValid: true,
        nonceSeen: true,
        timestampDriftMs: driftMs,
        crcValid: true,
        signerKeyId: keyId,
      };
    }

    // 6. Record Nonce & Enforce Bounded Cache
    this.nonceCache.set(nonceKey, receivedAtMs);
    this.pruneNonceCache(receivedAtMs);

    // 7. Return VERIFIED
    return {
      status: IntegrityStatus.VERIFIED,
      signatureAlgorithm: 'ED25519',
      signatureValid: true,
      nonceSeen: false,
      timestampDriftMs: driftMs,
      crcValid: true,
      signerKeyId: keyId,
    };
  }

  pruneNonceCache(currentTimeMs) {
    const cutoff = currentTimeMs - this.maxTimestampDriftMs * 2;

    // Prune expired entries
    for (const [key, timestamp] of this.nonceCache) {
      if (timestamp < cutoff) {
        this.nonceCache.delete(key);
      }
    }

    // Enforce hard capacity bounds with FIFO eviction
    while (this.nonceCache.size > this.maxNonceEntries) {
      const oldestKey = this.nonceCache.keys().next().value;
      if (oldestKey === undefined) break;
      this.nonceCache.delete(oldestKey);
    }
  }

  static hashPayload(payloadBytes) {
    return bytesToHex(sha256(payloadBytes));
  }
}
