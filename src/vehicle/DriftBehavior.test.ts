import RAPIER from '@dimforge/rapier3d-compat';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { RaycastVehicle } from './RaycastVehicle';

const neutral = {
  steer: 0,
  throttle: 0,
  brakeReverse: 0,
  handbrake: false,
  reset: false,
};

interface ManeuverResult {
  peakRearSlipRad: number;
  peakYawRateRadPerSec: number;
  minimumRearGrip: number;
  finalRearSlipRad: number;
  finalYawRateRadPerSec: number;
}

async function runManeuver(useHandbrake: boolean): Promise<ManeuverResult> {
  const physics = await createPhysicsRuntime();
  physics.world.createCollider(
    RAPIER.ColliderDesc.cuboid(120, 0.1, 120)
      .setTranslation(0, -0.1, 0)
      .setFriction(1.1),
  );
  physics.step(1 / 120);

  const vehicle = new RaycastVehicle(physics);
  for (let step = 0; step < 180; step += 1) {
    vehicle.preStep(neutral, 1 / 120);
    physics.step(1 / 120);
  }

  vehicle.body.setLinvel({ x: 0, y: 0, z: -16 }, true);
  let peakRearSlipRad = 0;
  let peakYawRateRadPerSec = 0;
  let minimumRearGrip = Number.POSITIVE_INFINITY;

  for (let step = 0; step < 120; step += 1) {
    vehicle.preStep(
      {
        ...neutral,
        steer: 0.8,
        throttle: 0.3,
        handbrake: useHandbrake && step < 72,
      },
      1 / 120,
    );
    physics.step(1 / 120);
    const telemetry = vehicle.telemetry();
    peakRearSlipRad = Math.max(peakRearSlipRad, telemetry.rearMaxAbsSlipAngleRad);
    peakYawRateRadPerSec = Math.max(peakYawRateRadPerSec, Math.abs(telemetry.yawRateRadPerSec));
    for (const wheel of telemetry.wheels) {
      if (wheel.axle === 'rear' && wheel.contact) {
        minimumRearGrip = Math.min(minimumRearGrip, wheel.gripCoefficient);
      }
    }
  }

  for (let step = 0; step < 180; step += 1) {
    const yawRate = vehicle.telemetry().yawRateRadPerSec;
    // With T015's semantic steering convention, yaw sign and semantic
    // countersteer sign match: negative/right yaw needs negative/left input.
    const countersteer = yawRate === 0 ? 0 : Math.sign(yawRate) * 0.55;
    vehicle.preStep(
      {
        ...neutral,
        steer: countersteer,
        throttle: 0.45,
      },
      1 / 120,
    );
    physics.step(1 / 120);
  }

  const final = vehicle.telemetry();
  const result = {
    peakRearSlipRad,
    peakYawRateRadPerSec,
    minimumRearGrip,
    finalRearSlipRad: final.rearMaxAbsSlipAngleRad,
    finalYawRateRadPerSec: Math.abs(final.yawRateRadPerSec),
  };
  vehicle.dispose();
  physics.dispose();
  return result;
}

describe('drift and handbrake behavior', () => {
  it('uses speed-dependent rear grip reduction and braking to increase rotation without scripted yaw', async () => {
    const baseline = await runManeuver(false);
    const handbrake = await runManeuver(true);

    expect(handbrake.minimumRearGrip).toBeLessThan(baseline.minimumRearGrip * 0.65);
    expect(handbrake.peakRearSlipRad).toBeGreaterThan(baseline.peakRearSlipRad + 0.03);
    expect(handbrake.peakYawRateRadPerSec).toBeGreaterThan(baseline.peakYawRateRadPerSec * 1.05);
  });

  it('allows countersteer and throttle to reduce the initiated slide after handbrake release', async () => {
    const handbrake = await runManeuver(true);
    expect(handbrake.peakRearSlipRad).toBeGreaterThan(0.08);
    expect(handbrake.finalRearSlipRad).toBeLessThan(handbrake.peakRearSlipRad);
    expect(handbrake.finalYawRateRadPerSec).toBeLessThan(handbrake.peakYawRateRadPerSec);
  });
});
