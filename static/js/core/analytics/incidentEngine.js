import { IntegrityStatus, EventSeverity } from '../types/events.js';

export class CyberIncidentEngine {
  constructor() {
    this.activeIncidents = new Map();
    this.incidentSequence = 42;
  }

  evaluateEventForIncident(event, scenarioStage = 1) {
    const isCriticalIntegrity =
      event.integrity.status === IntegrityStatus.INVALID_SIGNATURE ||
      event.integrity.status === IntegrityStatus.CRC_FAILURE;

    const isSevereAnomaly = event.analytics.anomalyScore >= 0.70 && event.analytics.trustScore <= 0.60;

    if (!isCriticalIntegrity && !isSevereAnomaly && scenarioStage < 6) {
      return null;
    }

    for (const incident of this.activeIncidents.values()) {
      if (incident.primaryNodeId === event.sourceId && incident.status !== 'RESOLVED') {
        incident.updatedAtMs = event.timestamp;
        incident.evidence.contributingEventIds.push(event.id);
        if (event.analytics.anomalyReasons.length > 0) {
          incident.evidence.anomalyReasons.push(...event.analytics.anomalyReasons);
        }

        if (scenarioStage === 6 && incident.status === 'DETECTED') {
          incident.status = 'TRIAGED';
        } else if (scenarioStage === 7 && incident.status === 'TRIAGED') {
          incident.status = 'INVESTIGATING';
        } else if (scenarioStage === 8 && incident.status !== 'CONTAINED') {
          incident.status = 'CONTAINED';
          incident.quarantined = true;
        }

        return incident;
      }
    }

    const incidentId = `ARG-${new Date().getFullYear()}-${String(this.incidentSequence++).padStart(4, '0')}`;
    const severity = isCriticalIntegrity ? EventSeverity.CRITICAL : EventSeverity.HIGH;
    const title = isCriticalIntegrity
      ? `Cryptographic Telemetry Compromise on ${event.sourceId}`
      : `Spatio-Kinematic Telemetry Spoofing on ${event.sourceId}`;

    const newIncident = {
      incidentId,
      title,
      severity,
      status: scenarioStage >= 7 ? 'INVESTIGATING' : scenarioStage === 6 ? 'TRIAGED' : 'DETECTED',
      detectedAtMs: event.timestamp,
      updatedAtMs: event.timestamp,
      primaryNodeId: event.sourceId,
      affectedEntities: [event.sourceId],
      centroid: { latitude: event.location.latitude, longitude: event.location.longitude },
      evidence: {
        integrityViolations: isCriticalIntegrity ? [event.integrity.status] : [],
        anomalyReasons: [...event.analytics.anomalyReasons],
        contributingEventIds: [event.id],
        trustScoreAtDetection: event.analytics.trustScore,
      },
      confidenceScore: isCriticalIntegrity ? 0.96 : 0.84,
      quarantined: scenarioStage === 8,
    };

    this.activeIncidents.set(incidentId, newIncident);
    return newIncident;
  }

  getActiveIncidents() {
    return Array.from(this.activeIncidents.values());
  }

  updateIncidentStatus(incidentId, status) {
    const incident = this.activeIncidents.get(incidentId);
    if (incident) {
      incident.status = status;
      incident.updatedAtMs = Date.now();
    }
  }

  setQuarantined(incidentId, quarantined) {
    const incident = this.activeIncidents.get(incidentId);
    if (incident) {
      incident.quarantined = quarantined;
      incident.status = quarantined ? 'CONTAINED' : 'INVESTIGATING';
      incident.updatedAtMs = Date.now();
    }
  }
}
