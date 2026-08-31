import type { VehicleAxle } from './VehicleConfig';

export interface TireForceInput {
  longitudinalVelocityMps: number;
  lateralVelocityMps: number;
  normalLoadN: number;
  driveForceN: number;
  brakeForceN: number;
  gripCoefficient: number;
  corneringStiffnessNPerMps: number;
}

export interface TireForceResult {
  longitudinalForceN: number;
  lateralForceN: number;
  gripLimitN: number;
  utilization: number;
  slipAngleRad: number;
}

function smoothLimit(value: number, limit: number): number {
  if (!(limit > 0)) return 0;
  return limit * Math.tanh(value / limit);
}

export function wheelDriveShare(axle: VehicleAxle, awdFrontBias: number): number {
  const frontBias = Math.min(1, Math.max(0, awdFrontBias));
  return axle === 'front' ? frontBias / 2 : (1 - frontBias) / 2;
}

export function computeTireForces(input: TireForceInput): TireForceResult {
  const gripLimitN = Math.max(0, input.normalLoadN * input.gripCoefficient);
  if (gripLimitN === 0) {
    return {
      longitudinalForceN: 0,
      lateralForceN: 0,
      gripLimitN: 0,
      utilization: 0,
      slipAngleRad: 0,
    };
  }

  const velocityDirection =
    Math.abs(input.longitudinalVelocityMps) > 0.25
      ? Math.sign(input.longitudinalVelocityMps)
      : Math.sign(input.driveForceN);
  const longitudinalDemandN =
    input.driveForceN - velocityDirection * Math.max(0, input.brakeForceN);
  const lateralDemandN =
    -input.lateralVelocityMps * Math.max(0, input.corneringStiffnessNPerMps);

  let longitudinalForceN = smoothLimit(longitudinalDemandN, gripLimitN);
  let lateralForceN = smoothLimit(lateralDemandN, gripLimitN);
  const magnitude = Math.hypot(longitudinalForceN, lateralForceN);
  if (magnitude > gripLimitN && magnitude > 0) {
    const scale = gripLimitN / magnitude;
    longitudinalForceN *= scale;
    lateralForceN *= scale;
  }

  const slipAngleRad = Math.atan2(
    input.lateralVelocityMps,
    Math.max(0.5, Math.abs(input.longitudinalVelocityMps)),
  );

  return {
    longitudinalForceN,
    lateralForceN,
    gripLimitN,
    utilization: Math.min(1, Math.hypot(longitudinalForceN, lateralForceN) / gripLimitN),
    slipAngleRad,
  };
}
