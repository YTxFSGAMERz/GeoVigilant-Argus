export class SpatialTemporalAnomalyDetector {
  constructor() {
    this.lastLocations = new Map();
    this.lastTimestamps = new Map();

    this.TEMP_MEAN = 24.0;
    this.TEMP_STD = 3.0;
    this.MAX_SPEED_MPS = 45.0;
    this.EXPECTED_INTERVAL_MS = 2000;
  }

  evaluate(event) {
    const reasons = [];
    let behavioralScore = 0.0;
    let kinematicScore = 0.0;
    let frequencyScore = 0.0;

    if (event.measurements && event.measurements.temperatureCelsius !== undefined) {
      const tempZ = Math.abs(event.measurements.temperatureCelsius - this.TEMP_MEAN) / this.TEMP_STD;
      if (tempZ > 3.0) {
        behavioralScore = Math.min(1.0, (tempZ - 3.0) / 3.0 + 0.5);
        reasons.push(`Temperature deviation Z-Score: ${tempZ.toFixed(2)} (${event.measurements.temperatureCelsius}°C)`);
      }
    }

    const lastLoc = this.lastLocations.get(event.sourceId);
    if (lastLoc) {
      const dtSeconds = Math.max(0.1, (event.timestamp - lastLoc.timestampMs) / 1000.0);
      const distanceMeters = this.haversineDistanceMeters(lastLoc.location, event.location);
      const calculatedSpeedMps = distanceMeters / dtSeconds;

      if (calculatedSpeedMps > this.MAX_SPEED_MPS) {
        kinematicScore = Math.min(1.0, (calculatedSpeedMps - this.MAX_SPEED_MPS) / 100.0 + 0.5);
        reasons.push(
          `Kinematic velocity anomaly: ${calculatedSpeedMps.toFixed(1)} m/s (Limit: ${this.MAX_SPEED_MPS} m/s, Dist: ${distanceMeters.toFixed(0)}m in ${dtSeconds.toFixed(1)}s)`
        );
      }
    }
    this.lastLocations.set(event.sourceId, { location: event.location, timestampMs: event.timestamp });

    const prevTime = this.lastTimestamps.get(event.sourceId);
    if (prevTime) {
      const interval = event.timestamp - prevTime;
      const deviation = Math.abs(interval - this.EXPECTED_INTERVAL_MS) / this.EXPECTED_INTERVAL_MS;
      if (deviation > 2.0) {
        frequencyScore = Math.min(1.0, deviation / 4.0);
        reasons.push(`Telemetry interval jitter: ${interval}ms`);
      }
    }
    this.lastTimestamps.set(event.sourceId, event.timestamp);

    const compositeScore = Number(
      Math.max(behavioralScore, kinematicScore, frequencyScore, (behavioralScore + kinematicScore + frequencyScore) / 2.0).toFixed(4)
    );

    return {
      isAnomaly: compositeScore > 0.40 || reasons.length > 0,
      compositeAnomalyScore: compositeScore,
      behavioralAnomalyScore: behavioralScore,
      kinematicAnomalyScore: kinematicScore,
      frequencyAnomalyScore: frequencyScore,
      reasons,
    };
  }

  haversineDistanceMeters(p1, p2) {
    const R = 6371000;
    const dLat = ((p2.latitude - p1.latitude) * Math.PI) / 180;
    const dLon = ((p2.longitude - p1.longitude) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((p1.latitude * Math.PI) / 180) *
        Math.cos((p2.latitude * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }
}
