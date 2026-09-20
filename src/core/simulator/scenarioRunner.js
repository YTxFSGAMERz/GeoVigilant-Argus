import * as ed from '@noble/ed25519';
import { SeededPRNG } from './prng.js';
import { ArgusFrameProtocol } from '../crypto/frameProtocol.js';
import { TelemetryIntegrityChecker } from '../crypto/integrity.js';
import { EventClass, IntegrityStatus, EventSeverity } from '../types/events.js';

export class ScenarioRunner {
  constructor(seed = 0x41524755) {
    this.prng = new SeededPRNG(seed);
    this.nodes = [];
    this.currentStage = 1;
    this.tickCount = 0;
    this.stageStartedAtTick = 0;
    this.initNodes();
  }

  initNodes() {
    for (let i = 1; i <= 3; i++) {
      const privSeed = new Uint8Array(32);
      for (let j = 0; j < 32; j++) {
        privSeed[j] = Math.floor(this.prng.nextRange(1, 255));
      }
      const pubKey = ed.getPublicKey(privSeed);

      // Coordinate cluster in San Francisco Bay Area (Tactical Demo Polygon)
      const latOffset = (i - 2) * 0.035;
      const lonOffset = (i - 2) * 0.025;

      this.nodes.push({
        nodeId: `NODE-00${i}`,
        privateKey: privSeed,
        publicKey: pubKey,
        baseLat: 37.7749 + latOffset,
        baseLon: -122.4194 + lonOffset,
        baseAlt: 15.0,
      });
    }
  }

  getPublicKeys() {
    const map = new Map();
    this.nodes.forEach((n) => map.set(n.nodeId, n.publicKey));
    return map;
  }

  setStage(stage) {
    const normalized = Math.max(1, Math.min(8, stage));
    if (normalized !== this.currentStage) {
      this.currentStage = normalized;
      this.stageStartedAtTick = this.tickCount;
    }
  }

  getCurrentStage() {
    return this.currentStage;
  }

  getStageTick() {
    return this.tickCount - this.stageStartedAtTick;
  }

  /**
   * Generates deterministic signed frames and normalized events.
   * @param {number} currentEpochMs
   * @param {boolean} forceCrcCorrupt
   * @returns {Array<Object>}
   */
  generateTickFrames(currentEpochMs, forceCrcCorrupt = false) {
    this.tickCount++;
    const stageTick = this.getStageTick();
    const frames = [];

    for (const node of this.nodes) {
      const isTarget = node.nodeId === 'NODE-002';
      let lat = node.baseLat + this.prng.nextGaussian(0, 0.00002);
      let lon = node.baseLon + this.prng.nextGaussian(0, 0.00002);
      let temp = 23.5 + this.prng.nextGaussian(0, 0.2);
      let tamperSignature = false;
      let corruptCrc = forceCrcCorrupt && isTarget;

      // Deterministic 8-Stage Scenario Progression for NODE-002
      if (isTarget) {
        switch (this.currentStage) {
          case 1: // Stage 1: Healthy normal telemetry
            break;
          case 2: // Stage 2: Monotonic sensor temperature drift
            temp = 23.5 + Math.min(26.0, stageTick * 1.2);
            break;
          case 3: // Stage 3: Kinematic GPS teleportation jump (~14 km)
            lat += 0.12;
            lon += 0.09;
            break;
          case 4: // Stage 4: Invalid Ed25519 signature (with recomputed valid CRC)
            tamperSignature = true;
            break;
          case 5: // Stage 5: Multi-vector compound anomaly (GPS jump + Temp drift + Invalid Signature)
            lat += 0.12;
            temp = 48.5;
            tamperSignature = true;
            break;
          case 6: // Stage 6: Incident threshold crossed (Sustained multi-vector attack)
          case 7: // Stage 7: Grounded AI Analyst explanation
          case 8: // Stage 8: Node quarantine active
            lat += 0.12;
            temp = 49.0;
            tamperSignature = true;
            break;
        }
      }

      const rawFields = {
        nodeId: node.nodeId,
        sequenceNumber: this.tickCount,
        timestampEpochMs: currentEpochMs,
        latitude: lat,
        longitude: lon,
        altitudeMm: Math.round(node.baseAlt * 1000),
        temperatureCelsius: temp,
        relativeHumidityPercent: 50.0,
        accelX_mG: 0,
        accelY_mG: 0,
        accelZ_mG: 1000,
        batteryMillivolts: 4120,
      };

      // 1. Pack frame
      const frameBytes = ArgusFrameProtocol.packFrame(rawFields, node.privateKey);

      // 2. Apply intentional signature tampering if flagged
      if (tamperSignature) {
        frameBytes[50] ^= 0xff;
        frameBytes[51] ^= 0xaa;

        // Recompute CRC so structural frame integrity passes and Ed25519 returns INVALID_SIGNATURE
        const newCrc = ArgusFrameProtocol.computeCrc16(frameBytes.subarray(0, 112));
        const view = new DataView(frameBytes.buffer, frameBytes.byteOffset, frameBytes.byteLength);
        view.setUint16(112, newCrc, false);
      }

      // 3. Apply intentional CRC corruption if requested
      if (corruptCrc) {
        frameBytes[112] ^= 0xff;
      }

      // 4. Unpack frame slice
      const unpacked = ArgusFrameProtocol.unpackFrame(frameBytes);
      const nonce = `${this.tickCount}`;
      const payloadHash = TelemetryIntegrityChecker.hashPayload(unpacked.rawPayloadBytes);

      const event = {
        id: `EVT-${node.nodeId}-${this.tickCount}`,
        sourceId: node.nodeId,
        sourceClass: EventClass.ARGUS_IOT_NODE,
        sourceProvider: 'ARGUS_SECURE_MESH',
        timestamp: currentEpochMs,
        receivedAt: currentEpochMs + 6,
        location: {
          latitude: unpacked.fields.latitude,
          longitude: unpacked.fields.longitude,
          altitudeMeters: unpacked.fields.altitudeMm / 1000.0,
        },
        measurements: {
          sequenceNumber: unpacked.fields.sequenceNumber,
          temperatureCelsius: unpacked.fields.temperatureCelsius,
          relativeHumidityPercent: unpacked.fields.relativeHumidityPercent,
          batteryVoltageMv: unpacked.fields.batteryMillivolts,
          batteryPercent: 92,
        },
        integrity: {
          status: IntegrityStatus.VERIFIED,
          signatureAlgorithm: 'ED25519',
          signatureValid: !tamperSignature,
          nonceSeen: false,
          timestampDriftMs: 6,
          crcValid: unpacked.crcValid,
        },
        analytics: {
          trustScore: 1.0,
          anomalyScore: 0.0,
          isAnomaly: false,
          anomalyReasons: [],
        },
        severity: EventSeverity.INFO,
        rawPayloadHash: payloadHash,
      };

      frames.push({
        event,
        rawPayloadBytes: unpacked.rawPayloadBytes,
        signatureBytes: unpacked.signatureBytes,
        nonce,
      });
    }

    return frames;
  }
}
