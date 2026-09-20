import * as ed from '@noble/ed25519';
import { sha256, sha512 } from '@noble/hashes/sha2.js';
import { bytesToHex } from '@noble/hashes/utils.js';
import { IntegrityStatus } from '../types/events.js';

if (ed.hashes) {
  ed.hashes.sha512 = sha512;
}

export class TelemetryIntegrityChecker {
  constructor(keyRegistry, maxTimestampDriftMs = 15000) {
    this.keyRegistry = keyRegistry;
    this.maxTimestampDriftMs = maxTimestampDriftMs;
    this.nonceCache = new Map();
    this.maxNonceEntries = 10000;
  }

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

    this.nonceCache.set(nonceKey, receivedAtMs);
    this.pruneNonceCache(receivedAtMs);

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

    for (const [key, timestamp] of this.nonceCache) {
      if (timestamp < cutoff) {
        this.nonceCache.delete(key);
      }
    }

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
