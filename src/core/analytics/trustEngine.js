import { IntegrityStatus } from '../types/events.js';

export class DeviceTrustEngine {
  constructor() {
    this.nodeStates = new Map();

    // Weighted composition: w1 + w2 + w3 + w4 = 1.00
    this.W_INTEGRITY = 0.40;
    this.W_BEHAVIOR = 0.25;
    this.W_KINEMATIC = 0.25;
    this.W_FREQUENCY = 0.10;

    this.RECOVERY_RATE = 0.02; // Asymptotic recovery coefficient (s^-1)
    this.PENALTY_STEP = 0.45;  // Instantaneous step reduction upon severe fault
  }

  getOrCreateNode(nodeId, initialTimestampMs) {
    let state = this.nodeStates.get(nodeId);
    if (!state) {
      state = {
        nodeId,
        compositeTrust: 1.0,
        integrityFactor: 1.0,
        behavioralFactor: 1.0,
        kinematicFactor: 1.0,
        frequencyFactor: 1.0,
        lastUpdatedMs: initialTimestampMs,
        isQuarantined: false,
        trustHistory: [{ timestamp: initialTimestampMs, score: 1.0 }],
      };
      this.nodeStates.set(nodeId, state);
    }
    return state;
  }

  evaluateTrust(
    nodeId,
    integrity,
    behavioralAnomalyScore,
    kinematicAnomalyScore,
    frequencyAnomalyScore,
    currentTimestampMs
  ) {
    const state = this.getOrCreateNode(nodeId, currentTimestampMs);

    if (state.isQuarantined) {
      state.compositeTrust = 0.0;
      state.lastUpdatedMs = currentTimestampMs;
      state.trustHistory.push({ timestamp: currentTimestampMs, score: 0.0 });
      return state;
    }

    const dtSeconds = Math.max(0.1, (currentTimestampMs - state.lastUpdatedMs) / 1000.0);

    // 1. Instantaneous Factor Calculations
    const integrityFactor =
      integrity.status === IntegrityStatus.VERIFIED
        ? 1.0
        : integrity.status === IntegrityStatus.REPLAYED || integrity.status === IntegrityStatus.STALE_TIMESTAMP
        ? 0.2
        : 0.0;

    const behavioralFactor = Math.max(0.0, 1.0 - behavioralAnomalyScore);
    const kinematicFactor = Math.max(0.0, 1.0 - kinematicAnomalyScore);
    const frequencyFactor = Math.max(0.0, 1.0 - frequencyAnomalyScore);

    const instantaneousScore =
      this.W_INTEGRITY * integrityFactor +
      this.W_BEHAVIOR * behavioralFactor +
      this.W_KINEMATIC * kinematicFactor +
      this.W_FREQUENCY * frequencyFactor;

    // 2. Asymmetric Evolution Dynamics
    let newScore = state.compositeTrust;
    if (instantaneousScore < state.compositeTrust) {
      const drop = Math.max(this.PENALTY_STEP * (1.0 - instantaneousScore), state.compositeTrust - instantaneousScore);
      newScore = Math.max(0.0, state.compositeTrust - drop);
    } else {
      newScore = state.compositeTrust + this.RECOVERY_RATE * (1.0 - state.compositeTrust) * dtSeconds;
      newScore = Math.min(1.0, Math.min(instantaneousScore, newScore));
    }

    state.compositeTrust = Number(newScore.toFixed(4));
    state.integrityFactor = Number(integrityFactor.toFixed(4));
    state.behavioralFactor = Number(behavioralFactor.toFixed(4));
    state.kinematicFactor = Number(kinematicFactor.toFixed(4));
    state.frequencyFactor = Number(frequencyFactor.toFixed(4));
    state.lastUpdatedMs = currentTimestampMs;

    state.trustHistory.push({ timestamp: currentTimestampMs, score: state.compositeTrust });
    if (state.trustHistory.length > 100) {
      state.trustHistory.shift();
    }

    return state;
  }

  setQuarantine(nodeId, quarantined, timestampMs = Date.now()) {
    const state = this.getOrCreateNode(nodeId, timestampMs);
    state.isQuarantined = quarantined;
    if (quarantined) {
      state.compositeTrust = 0.0;
      state.trustHistory.push({ timestamp: timestampMs, score: 0.0 });
    }
  }

  resetNode(nodeId, timestampMs) {
    const state = this.nodeStates.get(nodeId);
    if (state) {
      state.compositeTrust = 1.0;
      state.isQuarantined = false;
      state.integrityFactor = 1.0;
      state.behavioralFactor = 1.0;
      state.kinematicFactor = 1.0;
      state.frequencyFactor = 1.0;
      state.lastUpdatedMs = timestampMs;
      state.trustHistory = [{ timestamp: timestampMs, score: 1.0 }];
    }
  }
}
