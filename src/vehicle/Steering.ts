function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export interface SpeedSteeringConfig {
  fullStrengthBelowMps: number;
  highSpeedMps: number;
  minimumScale: number;
}

export function speedSteeringScale(
  speedMps: number,
  config: SpeedSteeringConfig,
): number {
  const low = Math.max(0, config.fullStrengthBelowMps);
  const high = Math.max(low + 0.001, config.highSpeedMps);
  const t = clamp01((Math.max(0, speedMps) - low) / (high - low));
  const smooth = t * t * (3 - 2 * t);
  return 1 + (Math.min(1, Math.max(0, config.minimumScale)) - 1) * smooth;
}

export function ackermannWheelSteerAngle(
  centerSteerRad: number,
  wheelbaseM: number,
  trackM: number,
  wheelLocalX: number,
): number {
  const magnitude = Math.abs(centerSteerRad);
  if (magnitude < 1e-6) return 0;

  const halfTrack = Math.max(0, trackM) / 2;
  const centerRadius = Math.max(
    halfTrack + 0.05,
    Math.max(0.05, wheelbaseM) / Math.tan(magnitude),
  );
  // Positive physical steering rotates the -Z vehicle-forward axis left. Therefore
  // the left wheel (negative local X) is inside on positive/left turns; the right
  // wheel is inside on negative/right turns. Semantic input sign is handled by the
  // vehicle before this function is called.
  const inside =
    (centerSteerRad > 0 && wheelLocalX < 0) ||
    (centerSteerRad < 0 && wheelLocalX > 0);
  const wheelRadius = Math.max(
    0.05,
    centerRadius + (inside ? -halfTrack : halfTrack),
  );
  return Math.sign(centerSteerRad) * Math.atan(Math.max(0.05, wheelbaseM) / wheelRadius);
}
