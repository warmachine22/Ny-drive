import { describe, expect, it } from 'vitest';
import { computeTireForces, wheelDriveShare } from './TireForces';

function lateralForceAt(lateralVelocityMps: number): number {
  return Math.abs(
    computeTireForces({
      longitudinalVelocityMps: 12,
      lateralVelocityMps,
      normalLoadN: 3200,
      driveForceN: 0,
      brakeForceN: 0,
      gripCoefficient: 1.1,
      corneringStiffnessNPerMps: 2500,
    }).lateralForceN,
  );
}

describe('tire force model', () => {
  it('distributes AWD torque by configurable axle bias', () => {
    expect(wheelDriveShare('front', 0.45)).toBeCloseTo(0.225);
    expect(wheelDriveShare('rear', 0.45)).toBeCloseTo(0.275);
    expect(
      wheelDriveShare('front', 0.45) * 2 + wheelDriveShare('rear', 0.45) * 2,
    ).toBeCloseTo(1);
  });

  it('opposes lateral slip and respects a combined progressive grip limit', () => {
    const result = computeTireForces({
      longitudinalVelocityMps: 12,
      lateralVelocityMps: 4,
      normalLoadN: 3200,
      driveForceN: 5000,
      brakeForceN: 0,
      gripCoefficient: 1.1,
      corneringStiffnessNPerMps: 2500,
    });

    expect(result.lateralForceN).toBeLessThan(0);
    expect(result.longitudinalForceN).toBeGreaterThan(0);
    expect(Math.hypot(result.longitudinalForceN, result.lateralForceN)).toBeLessThanOrEqual(
      result.gripLimitN + 0.001,
    );
    expect(result.utilization).toBeGreaterThan(0.5);
    expect(result.slipAngleRad).toBeGreaterThan(0);
  });

  it('approaches the lateral grip limit smoothly rather than switching traction on and off', () => {
    const low = lateralForceAt(0.2);
    const medium = lateralForceAt(0.8);
    const high = lateralForceAt(4);
    const veryHigh = lateralForceAt(12);

    expect(low).toBeGreaterThan(0);
    expect(medium).toBeGreaterThan(low);
    expect(high).toBeGreaterThan(medium);
    expect(veryHigh).toBeGreaterThanOrEqual(high);
    expect(veryHigh - high).toBeLessThan(high - medium);
  });

  it('produces no tire force without normal load', () => {
    expect(
      computeTireForces({
        longitudinalVelocityMps: 5,
        lateralVelocityMps: 2,
        normalLoadN: 0,
        driveForceN: 4000,
        brakeForceN: 0,
        gripCoefficient: 1.1,
        corneringStiffnessNPerMps: 2000,
      }),
    ).toMatchObject({
      longitudinalForceN: 0,
      lateralForceN: 0,
      gripLimitN: 0,
      utilization: 0,
    });
  });
});
