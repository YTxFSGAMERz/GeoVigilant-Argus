import { IntegrityStatus } from '../types/events.js';

export class PanopticAIAnalyst {
  analyzeIncident(incident) {
    const facts = [
      `Node ${incident.primaryNodeId} triggered incident ${incident.incidentId} (Lifecycle Status: ${incident.status}).`,
      `Initial trust score collapsed to ${(incident.evidence.trustScoreAtDetection * 100).toFixed(1)}%.`,
      ...incident.evidence.integrityViolations.map((v) => `Telemetry integrity failure recorded: ${v}.`),
      ...incident.evidence.anomalyReasons.map((r) => `Deterministic anomaly metric: ${r}.`),
    ];

    const inferences = [];
    const hypotheses = [];
    const actions = [];

    if (incident.evidence.integrityViolations.includes(IntegrityStatus.INVALID_SIGNATURE)) {
      inferences.push(
        `Payload signature does not match registered Ed25519 public key for ${incident.primaryNodeId}; frame is unauthenticated.`
      );
      hypotheses.push(
        'Rogue node transmitting telemetry frames using spoofed node ID without corresponding private key.',
        'Firmware key storage corrupted or physical flash memory compromised.'
      );
      actions.push({
        actionType: 'NODE_QUARANTINE',
        targetEntity: incident.primaryNodeId,
        rationale: 'Isolate node to prevent unauthenticated telemetry from polluting sensor fusion.',
        urgency: 'IMMEDIATE',
      });
      actions.push({
        actionType: 'KEY_REVOCATION',
        targetEntity: incident.primaryNodeId,
        rationale: 'Mark public key in NodeIdentityRegistry as invalid pending re-authentication.',
        urgency: 'HIGH',
      });
    } else {
      inferences.push('Kinematic velocity exceeds physical limits for stationary/low-speed IoT hardware.');
      hypotheses.push(
        'GPS receiver multi-path interference or intentional GNSS RF spoofing in local operational area.',
        'Sensor firmware coordinate calculation buffer overflow.'
      );
      actions.push({
        actionType: 'NODE_QUARANTINE',
        targetEntity: incident.primaryNodeId,
        rationale: 'Isolate node until coordinate baseline stabilizes.',
        urgency: 'IMMEDIATE',
      });
    }

    return {
      incidentId: incident.incidentId,
      title: incident.title,
      confidenceScore: incident.confidenceScore,
      observedFacts: facts,
      inferences,
      hypotheses,
      recommendedActions: actions,
    };
  }
}
