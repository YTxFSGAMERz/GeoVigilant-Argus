import * as ed from '@noble/ed25519';
import { sha512 } from '@noble/hashes/sha2.js';

// Configure synchronous SHA-512 for noble/ed25519
if (ed.hashes) {
  ed.hashes.sha512 = sha512;
}

export const FRAME_CONSTANTS = {
  MAGIC: 0xaa55,
  PROTO_VERSION: 0x01,
  MSG_TELEMETRY: 0x01,
  PAYLOAD_SIZE: 48,
  SIGNATURE_SIZE: 64,
  CRC_SIZE: 2,
  TOTAL_FRAME_SIZE: 114, // 48 + 64 + 2
};

export class ArgusFrameProtocol {
  /**
   * Computes CRC-16-CCITT (Polynomial 0x1021, Initial Value 0xFFFF).
   * @param {Uint8Array} data
   * @returns {number}
   */
  static computeCrc16(data) {
    let crc = 0xffff;
    for (let i = 0; i < data.length; i++) {
      crc ^= data[i] << 8;
      for (let j = 0; j < 8; j++) {
        if ((crc & 0x8000) !== 0) {
          crc = ((crc << 1) ^ 0x1021) & 0xffff;
        } else {
          crc = (crc << 1) & 0xffff;
        }
      }
    }
    return crc;
  }

  /**
   * Serializes raw telemetry fields into a canonical 48-byte payload buffer.
   * @param {Object} fields
   * @returns {Uint8Array}
   */
  static serializePayload(fields) {
    const buffer = new ArrayBuffer(FRAME_CONSTANTS.PAYLOAD_SIZE);
    const view = new DataView(buffer);

    // Header (0x00 - 0x03)
    view.setUint16(0, FRAME_CONSTANTS.MAGIC, false);
    view.setUint8(2, FRAME_CONSTANTS.PROTO_VERSION);
    view.setUint8(3, FRAME_CONSTANTS.MSG_TELEMETRY);

    // Node ID (0x04 - 0x0B) - 8 bytes ASCII null-padded
    const enc = new TextEncoder();
    const idBytes = enc.encode(fields.nodeId || 'NODE-000');
    const idView = new Uint8Array(buffer, 4, 8);
    idView.fill(0);
    idView.set(idBytes.subarray(0, 8));

    // Sequence Number & Timestamp (0x0C - 0x17)
    view.setUint32(12, fields.sequenceNumber || 0, false);
    view.setBigUint64(16, BigInt(fields.timestampEpochMs || 0), false);

    // Position & Kinematics (0x18 - 0x23)
    view.setInt32(24, Math.round((fields.latitude || 0) * 1e7), false);
    view.setInt32(28, Math.round((fields.longitude || 0) * 1e7), false);
    view.setInt32(32, fields.altitudeMm || 0, false);

    // Environmental & Inertial Telemetry (0x24 - 0x2F)
    view.setInt16(36, Math.round((fields.temperatureCelsius || 0) * 100), false);
    view.setUint16(38, Math.round((fields.relativeHumidityPercent || 0) * 10), false);
    view.setInt16(40, fields.accelX_mG || 0, false);
    view.setInt16(42, fields.accelY_mG || 0, false);
    view.setInt16(44, fields.accelZ_mG || 0, false);
    view.setUint16(46, fields.batteryMillivolts || 0, false);

    return new Uint8Array(buffer);
  }

  /**
   * Packs and signs a complete 114-byte wire frame.
   * @param {Object} fields
   * @param {Uint8Array} privateKey
   * @returns {Uint8Array}
   */
  static packFrame(fields, privateKey) {
    const payloadBytes = this.serializePayload(fields);
    const signature = ed.sign(payloadBytes, privateKey);

    const frame = new Uint8Array(FRAME_CONSTANTS.TOTAL_FRAME_SIZE);
    frame.set(payloadBytes, 0);
    frame.set(signature, FRAME_CONSTANTS.PAYLOAD_SIZE);

    // Compute CRC-16 over first 112 bytes (Payload + Signature)
    const crc = this.computeCrc16(frame.subarray(0, 112));
    const view = new DataView(frame.buffer, frame.byteOffset, frame.byteLength);
    view.setUint16(112, crc, false);

    return frame;
  }

  /**
   * Unpacks a 114-byte frame, validates structural CRC-16, and extracts payload & signature slices.
   * @param {Uint8Array} frameBytes
   * @returns {Object}
   */
  static unpackFrame(frameBytes) {
    if (frameBytes.length !== FRAME_CONSTANTS.TOTAL_FRAME_SIZE) {
      throw new Error(`Invalid frame size: expected ${FRAME_CONSTANTS.TOTAL_FRAME_SIZE}, got ${frameBytes.length}`);
    }

    const view = new DataView(frameBytes.buffer, frameBytes.byteOffset, frameBytes.byteLength);

    // Validate Magic Sync Header
    const magic = view.getUint16(0, false);
    if (magic !== FRAME_CONSTANTS.MAGIC) {
      throw new Error(`Invalid magic sync bytes: 0x${magic.toString(16)}`);
    }

    // Validate CRC-16
    const expectedCrc = this.computeCrc16(frameBytes.subarray(0, 112));
    const actualCrc = view.getUint16(112, false);
    const crcValid = expectedCrc === actualCrc;

    // Extract ASCII Node ID
    const idBytes = frameBytes.subarray(4, 12);
    let nullIdx = idBytes.indexOf(0);
    if (nullIdx === -1) nullIdx = 8;
    const nodeId = new TextDecoder().decode(idBytes.subarray(0, nullIdx));

    const fields = {
      nodeId,
      sequenceNumber: view.getUint32(12, false),
      timestampEpochMs: Number(view.getBigUint64(16, false)),
      latitude: view.getInt32(24, false) / 1e7,
      longitude: view.getInt32(28, false) / 1e7,
      altitudeMm: view.getInt32(32, false),
      temperatureCelsius: view.getInt16(36, false) / 100,
      relativeHumidityPercent: view.getUint16(38, false) / 10,
      accelX_mG: view.getInt16(40, false),
      accelY_mG: view.getInt16(42, false),
      accelZ_mG: view.getInt16(44, false),
      batteryMillivolts: view.getUint16(46, false),
    };

    return {
      fields,
      rawPayloadBytes: frameBytes.slice(0, FRAME_CONSTANTS.PAYLOAD_SIZE),
      signatureBytes: frameBytes.slice(FRAME_CONSTANTS.PAYLOAD_SIZE, 112),
      crcValid,
    };
  }
}
