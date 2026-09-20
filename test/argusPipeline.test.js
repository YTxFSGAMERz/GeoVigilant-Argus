import { describe, it, expect, beforeEach } from 'vitest';
import * as ed from '@noble/ed25519';
import { sha512 } from '@noble/hashes/sha2.js';
import { createArgusRuntime } from '../src/core/runtime.js';
import { ArgusFrameProtocol } from '../src/core/crypto/frameProtocol.js';
import { TelemetryIntegrityChecker } from '../src/core/crypto/integrity.js';
import { IntegrityStatus } from '../src/core/types/events.js';

if (ed.hashes) {
  ed.hashes.sha512 = sha512;
}

describe('ARGUS Pipeline, Cryptographic Protocol & Anomaly State Machine', () => {
  let runtime;

  beforeEach(() => {
    runtime = createArgusRuntime(0x1337);
  });

  it('1. Serializes, signs, and unpacks 114-byte frames with valid CRC-16', () => {
    const privKey = new Uint8Array(32).fill(5);
    const fields = {
      nodeId: 'NODE-001',
      sequenceNumber: 42,
      timestampEpochMs: 1723974869000,
      latitude: 37.774929,
      longitude: -122.419416,
      altitudeMm: 15200,
      temperatureCelsius: 24.5,
      relativeHumidityPercent: 55.0,
      accelX_mG: 10,
      accelY_mG: -5,
      accelZ_mG: 995,
      batteryMillivolts: 4150,
    };

    const packed = ArgusFrameProtocol.packFrame(fields, privKey);
    expect(packed.length).toBe(114);

    const unpacked = ArgusFrameProtocol.unpackFrame(packed);
    expect(unpacked.crcValid).toBe(true);
    expect(unpacked.fields.nodeId).toBe('NODE-001');
    expect(unpacked.fields.sequenceNumber).toBe(42);
    expect(unpacked.fields.latitude).toBeCloseTo(37.774929, 5);
    expect(unpacked.fields.longitude).toBeCloseTo(-122.419416, 5);
  });

  it('2. Rejects CRC failures, unknown nodes, forged signatures, stale timestamps, and replays in strict order', () => {
    const privKey = new Uint8Array(32).fill(3);
    const pubKey = ed.getPublicKey(privKey);
    const registry = { getPublicKey: (id) => (id === 'NODE-001' ? pubKey : undefined) };
    const checker = new TelemetryIntegrityChecker(registry, 5000);

    const payload = new Uint8Array(48).fill(0xbb);
    const validSig = ed.sign(payload, privKey);

    // [A] CRC Failure
    const rCrc = checker.verifyFrame('NODE-001', payload, validSig, 'nonce-0', 10000, 10050, false);
    expect(rCrc.status).toBe(IntegrityStatus.CRC_FAILURE);

    // [B] Unknown Node
    const rUnknown = checker.verifyFrame('UNKNOWN-99', payload, validSig, 'nonce-0', 10000, 10050, true);
    expect(rUnknown.status).toBe(IntegrityStatus.UNKNOWN_NODE);

    // [C] Forged Signature
    const forgedSig = new Uint8Array(validSig);
    forgedSig[0] ^= 0xff;
    const rSig = checker.verifyFrame('NODE-001', payload, forgedSig, 'nonce-1', 10000, 10050, true);
    expect(rSig.status).toBe(IntegrityStatus.INVALID_SIGNATURE);

    // [D] Stale Timestamp (Drift > 5000ms)
    const rStale = checker.verifyFrame('NODE-001', payload, validSig, 'nonce-2', 10000, 20000, true);
    expect(rStale.status).toBe(IntegrityStatus.STALE_TIMESTAMP);

    // [E] Valid Frame
    const rValid = checker.verifyFrame('NODE-001', payload, validSig, 'nonce-3', 10000, 10050, true);
    expect(rValid.status).toBe(IntegrityStatus.VERIFIED);

    // [F] Replayed Nonce
    const rReplay = checker.verifyFrame('NODE-001', payload, validSig, 'nonce-3', 10000, 10050, true);
    expect(rReplay.status).toBe(IntegrityStatus.REPLAYED);
  });

  it('3. Stage 4 produces INVALID_SIGNATURE with crcValid = true', () => {
    runtime.scenarioRunner.setStage(4);
    const frames = runtime.scenarioRunner.generateTickFrames(1000);
    const n2 = frames.find((f) => f.event.sourceId === 'NODE-002');
    expect(n2).toBeDefined();

    const res = runtime.integrityChecker.verifyFrame(
      n2.event.sourceId,
      n2.rawPayloadBytes,
      n2.signatureBytes,
      n2.nonce,
      n2.event.timestamp,
      n2.event.receivedAt,
      n2.event.integrity.crcValid // Passes true because CRC was recomputed after tampering
    );

    expect(n2.event.integrity.crcValid).toBe(true);
    expect(res.status).toBe(IntegrityStatus.INVALID_SIGNATURE);
  });

  it('4. Dedicated CRC corruption correctly produces CRC_FAILURE', () => {
    runtime.scenarioRunner.setStage(1);
    const frames = runtime.scenarioRunner.generateTickFrames(1000, true); // force CRC corruption
    const n2 = frames.find((f) => f.event.sourceId === 'NODE-002');
    expect(n2.event.integrity.crcValid).toBe(false);

    const res = runtime.integrityChecker.verifyFrame(
      n2.event.sourceId,
      n2.rawPayloadBytes,
      n2.signatureBytes,
      n2.nonce,
      n2.event.timestamp,
      n2.event.receivedAt,
      n2.event.integrity.crcValid
    );
    expect(res.status).toBe(IntegrityStatus.CRC_FAILURE);
  });

  it('5. Stage 2 executes monotonic temperature drift without sawtooth resets', () => {
    runtime.scenarioRunner.setStage(2);
    const temps = [];

    for (let i = 0; i < 10; i++) {
      const frames = runtime.scenarioRunner.generateTickFrames(1000 + i * 1000);
      const n2 = frames.find((f) => f.event.sourceId === 'NODE-002');
      temps.push(n2.event.measurements.temperatureCelsius);
    }

    // Verify temperature strictly increases monotonically
    for (let i = 1; i < temps.length; i++) {
      expect(temps[i]).toBeGreaterThan(temps[i - 1]);
    }
  });

  it('6. Incident lifecycle transitions cleanly from DETECTED to CONTAINED', () => {
    // Stage 6: Incident Created
    runtime.scenarioRunner.setStage(6);
    const frames6 = runtime.scenarioRunner.generateTickFrames(1000);
    const n2 = frames6.find((f) => f.event.sourceId === 'NODE-002');
    n2.event.analytics.trustScore = 0.2;
    n2.event.analytics.anomalyScore = 0.85;

    const inc6 = runtime.incidentEngine.evaluateEventForIncident(n2.event, 6);
    expect(inc6).not.toBeNull();
    expect(inc6.status).toBe('TRIAGED');

    // Stage 7: AI Analysis triggered
    const analysis = runtime.aiAnalyst.analyzeIncident(inc6);
    expect(analysis.observedFacts.length).toBeGreaterThan(0);
    expect(analysis.recommendedActions[0].actionType).toBe('NODE_QUARANTINE');

    // Stage 8: Quarantine
    runtime.trustEngine.setQuarantine('NODE-002', true);
    runtime.incidentEngine.setQuarantined(inc6.incidentId, true);
    expect(inc6.status).toBe('CONTAINED');
    expect(runtime.trustEngine.getOrCreateNode('NODE-002', 1000).compositeTrust).toBe(0.0);
  });
});
