import { ScenarioRunner } from './simulator/scenarioRunner.js';
import { TelemetryIntegrityChecker } from './crypto/integrity.js';
import { DeviceTrustEngine } from './analytics/trustEngine.js';
import { SpatialTemporalAnomalyDetector } from './analytics/anomalyDetector.js';
import { CyberIncidentEngine } from './analytics/incidentEngine.js';
import { PanopticAIAnalyst } from './ai/panopticAnalyst.js';

export function createArgusRuntime(seed = 0x41524755) {
  const scenarioRunner = new ScenarioRunner(seed);
  const keyRegistry = {
    getPublicKey: (id) => scenarioRunner.getPublicKeys().get(id),
  };

  return {
    scenarioRunner,
    integrityChecker: new TelemetryIntegrityChecker(keyRegistry),
    trustEngine: new DeviceTrustEngine(),
    anomalyDetector: new SpatialTemporalAnomalyDetector(),
    incidentEngine: new CyberIncidentEngine(),
    aiAnalyst: new PanopticAIAnalyst(),
  };
}
