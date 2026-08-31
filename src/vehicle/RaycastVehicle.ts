import RAPIER from '@dimforge/rapier3d-compat';
import * as THREE from 'three';
import type { DrivingInputSnapshot } from '../input/actions';
import type { PhysicsRuntime } from '../physics/PhysicsWorld';
import { ackermannWheelSteerAngle, speedSteeringScale } from './Steering';
import { computeTireForces, wheelDriveShare } from './TireForces';
import {
  GC8_PROTOTYPE_CONFIG,
  type VehicleAxle,
  type VehicleConfig,
} from './VehicleConfig';

type RapierWorld = PhysicsRuntime['world'];
type RapierRigidBody = ReturnType<RapierWorld['createRigidBody']>;
type RapierCollider = ReturnType<RapierWorld['createCollider']>;

export interface VehicleLocalPosition {
  x: number;
  y: number;
  z: number;
}

export interface VehicleWheelTelemetry {
  id: string;
  axle: VehicleAxle;
  contact: boolean;
  suspensionLengthM: number;
  normalLoadN: number;
  longitudinalVelocityMps: number;
  lateralVelocityMps: number;
  longitudinalForceN: number;
  lateralForceN: number;
  slipAngleRad: number;
  gripCoefficient: number;
}

export interface VehicleTelemetry {
  speedMps: number;
  steeringAngleRad: number;
  yawRateRadPerSec: number;
  contactCount: number;
  maxAbsSlipAngleRad: number;
  rearMaxAbsSlipAngleRad: number;
  handbrakeActive: boolean;
  wheels: VehicleWheelTelemetry[];
}

interface WheelState {
  id: string;
  axle: VehicleAxle;
  localMount: THREE.Vector3;
  lastSuspensionLengthM: number;
  telemetry: VehicleWheelTelemetry;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function inverseLerpClamped(start: number, end: number, value: number): number {
  if (end <= start) return value >= end ? 1 : 0;
  return clamp((value - start) / (end - start), 0, 1);
}

function toThreeQuaternion(rotation: { x: number; y: number; z: number; w: number }): THREE.Quaternion {
  return new THREE.Quaternion(rotation.x, rotation.y, rotation.z, rotation.w);
}

function toRapierVector(vector: THREE.Vector3): { x: number; y: number; z: number } {
  return { x: vector.x, y: vector.y, z: vector.z };
}

export class RaycastVehicle {
  readonly body: RapierRigidBody;
  readonly chassisCollider: RapierCollider;
  private readonly wheels: WheelState[];
  private steeringAngleRad = 0;
  private handbrakeActive = false;

  constructor(
    private readonly physics: PhysicsRuntime,
    spawn: { x: number; z: number; y?: number } = { x: 0, z: 0 },
    readonly config: Readonly<VehicleConfig> = GC8_PROTOTYPE_CONFIG,
  ) {
    const bodyDesc = RAPIER.RigidBodyDesc.dynamic()
      .setTranslation(spawn.x, spawn.y ?? config.spawnHeightM, spawn.z)
      .setAdditionalMassProperties(
        config.massKg,
        { x: 0, y: config.centerOfMassY, z: 0 },
        config.principalInertiaKgM2,
        { w: 1, x: 0, y: 0, z: 0 },
      )
      .setLinearDamping(config.linearDamping)
      .setAngularDamping(config.angularDamping)
      .setCcdEnabled(true)
      .setCanSleep(false)
      .setAdditionalSolverIterations(2);
    this.body = physics.world.createRigidBody(bodyDesc);

    const half = config.chassisHalfExtentsM;
    this.chassisCollider = physics.world.createCollider(
      RAPIER.ColliderDesc.cuboid(half.x, half.y, half.z)
        .setDensity(0)
        .setFriction(0.35)
        .setRestitution(0),
      this.body,
    );

    const halfTrack = config.trackM / 2;
    const halfWheelbase = config.wheelbaseM / 2;
    const rest = config.suspensionRestLengthM;
    this.wheels = [
      this.createWheel('front-left', 'front', -halfTrack, -halfWheelbase, rest),
      this.createWheel('front-right', 'front', halfTrack, -halfWheelbase, rest),
      this.createWheel('rear-left', 'rear', -halfTrack, halfWheelbase, rest),
      this.createWheel('rear-right', 'rear', halfTrack, halfWheelbase, rest),
    ];
  }

  private createWheel(
    id: string,
    axle: VehicleAxle,
    x: number,
    z: number,
    restLengthM: number,
  ): WheelState {
    return {
      id,
      axle,
      localMount: new THREE.Vector3(x, this.config.suspensionMountY, z),
      lastSuspensionLengthM: restLengthM,
      telemetry: {
        id,
        axle,
        contact: false,
        suspensionLengthM: restLengthM,
        normalLoadN: 0,
        longitudinalVelocityMps: 0,
        lateralVelocityMps: 0,
        longitudinalForceN: 0,
        lateralForceN: 0,
        slipAngleRad: 0,
        gripCoefficient: this.config.tireGripCoefficient,
      },
    };
  }

  preStep(input: DrivingInputSnapshot, deltaSeconds: number): void {
    if (!(deltaSeconds > 0)) return;
    this.body.resetForces(true);
    this.body.resetTorques(true);
    this.handbrakeActive = input.handbrake;

    const translation = this.body.translation();
    const bodyPosition = new THREE.Vector3(translation.x, translation.y, translation.z);
    const bodyRotation = toThreeQuaternion(this.body.rotation());
    const bodyUp = new THREE.Vector3(0, 1, 0).applyQuaternion(bodyRotation).normalize();
    const suspensionDirection = bodyUp.clone().negate();
    const bodyForward = new THREE.Vector3(0, 0, -1).applyQuaternion(bodyRotation).normalize();
    const bodyRight = new THREE.Vector3(1, 0, 0).applyQuaternion(bodyRotation).normalize();
    const linearVelocity = this.body.linvel();
    const horizontalSpeed = Math.hypot(linearVelocity.x, linearVelocity.z);
    const steeringScale = speedSteeringScale(horizontalSpeed, {
      fullStrengthBelowMps: this.config.fullSteerBelowMps,
      highSpeedMps: this.config.highSpeedSteerMps,
      minimumScale: this.config.minimumSteerScale,
    });
    // Preserve T015's corrected semantic convention: positive input is a visual
    // right turn, while positive Three.js rotation about +Y turns -Z forward left.
    this.steeringAngleRad = -input.steer * this.config.maxSteerRad * steeringScale;

    const minSuspensionLength = Math.max(
      0.02,
      this.config.suspensionRestLengthM - this.config.suspensionTravelM,
    );
    const maxSuspensionLength =
      this.config.suspensionRestLengthM + this.config.suspensionTravelM;
    const rayLength = maxSuspensionLength + this.config.wheelRadiusM;

    for (const wheel of this.wheels) {
      const mount = wheel.localMount.clone().applyQuaternion(bodyRotation).add(bodyPosition);
      const ray = new RAPIER.Ray(toRapierVector(mount), toRapierVector(suspensionDirection));
      const hit = this.physics.world.castRayAndGetNormal(
        ray,
        rayLength,
        false,
        undefined,
        undefined,
        this.chassisCollider,
        this.body,
      );

      if (!hit) {
        wheel.lastSuspensionLengthM = maxSuspensionLength;
        wheel.telemetry = {
          ...wheel.telemetry,
          contact: false,
          suspensionLengthM: maxSuspensionLength,
          normalLoadN: 0,
          longitudinalVelocityMps: 0,
          lateralVelocityMps: 0,
          longitudinalForceN: 0,
          lateralForceN: 0,
          slipAngleRad: 0,
        };
        continue;
      }

      const contactNormal = new THREE.Vector3(hit.normal.x, hit.normal.y, hit.normal.z).normalize();
      if (contactNormal.dot(bodyUp) < 0.35) {
        wheel.lastSuspensionLengthM = maxSuspensionLength;
        wheel.telemetry = {
          ...wheel.telemetry,
          contact: false,
          suspensionLengthM: maxSuspensionLength,
          normalLoadN: 0,
          longitudinalVelocityMps: 0,
          lateralVelocityMps: 0,
          longitudinalForceN: 0,
          lateralForceN: 0,
          slipAngleRad: 0,
        };
        continue;
      }

      const suspensionLengthM = clamp(
        hit.timeOfImpact - this.config.wheelRadiusM,
        minSuspensionLength,
        maxSuspensionLength,
      );
      const compressionM = this.config.suspensionRestLengthM - suspensionLengthM;
      const compressionVelocityMps =
        (wheel.lastSuspensionLengthM - suspensionLengthM) / deltaSeconds;
      wheel.lastSuspensionLengthM = suspensionLengthM;
      const normalLoadN = clamp(
        compressionM * this.config.springRateNPerM +
          compressionVelocityMps * this.config.damperRateNsPerM,
        0,
        this.config.maxSuspensionForceN,
      );

      const contactPoint = mount
        .clone()
        .addScaledVector(suspensionDirection, hit.timeOfImpact);
      const pointVelocityRaw = this.body.velocityAtPoint(toRapierVector(contactPoint));
      const pointVelocity = new THREE.Vector3(
        pointVelocityRaw.x,
        pointVelocityRaw.y,
        pointVelocityRaw.z,
      );

      const wheelSteerAngle =
        wheel.axle === 'front'
          ? ackermannWheelSteerAngle(
              this.steeringAngleRad,
              this.config.wheelbaseM,
              this.config.trackM,
              wheel.localMount.x,
            )
          : 0;
      const steerRotation = new THREE.Quaternion().setFromAxisAngle(bodyUp, wheelSteerAngle);
      const wheelForward = bodyForward.clone().applyQuaternion(steerRotation).normalize();
      const wheelRight = bodyRight.clone().applyQuaternion(steerRotation).normalize();
      const longitudinalVelocityMps = pointVelocity.dot(wheelForward);
      const lateralVelocityMps = pointVelocity.dot(wheelRight);
      const driveShare = wheelDriveShare(wheel.axle, this.config.awdFrontBias);
      const rearHandbrake = wheel.axle === 'rear' && input.handbrake;
      const handbrakeSlideBlend = rearHandbrake
        ? inverseLerpClamped(
            this.config.handbrakeSlideStartMps,
            this.config.handbrakeSlideFullMps,
            Math.abs(longitudinalVelocityMps),
          )
        : 0;

      let driveForceN = input.throttle * this.config.maxDriveForceN * driveShare;
      if (rearHandbrake) driveForceN *= this.config.handbrakeRearDriveScale;

      let brakeForceN = 0;
      if (input.brakeReverse > 0) {
        if (Math.abs(longitudinalVelocityMps) > 1 || input.throttle > 0) {
          brakeForceN = (input.brakeReverse * this.config.maxBrakeForceN) / 4;
        } else {
          driveForceN -= input.brakeReverse * this.config.maxReverseForceN * driveShare;
        }
      }
      if (rearHandbrake) {
        brakeForceN += this.config.handbrakeRearBrakeForceN / 2;
      }

      const axleGripScale =
        wheel.axle === 'front' ? this.config.frontGripScale : this.config.rearGripScale;
      const axleCorneringScale =
        wheel.axle === 'front'
          ? this.config.frontCorneringScale
          : this.config.rearCorneringScale;
      const gripCoefficient =
        this.config.tireGripCoefficient *
        axleGripScale *
        THREE.MathUtils.lerp(1, this.config.handbrakeRearGripScale, handbrakeSlideBlend);
      const corneringStiffnessNPerMps =
        this.config.corneringStiffnessNPerMps *
        axleCorneringScale *
        THREE.MathUtils.lerp(1, this.config.handbrakeRearCorneringScale, handbrakeSlideBlend);

      const tire = computeTireForces({
        longitudinalVelocityMps,
        lateralVelocityMps,
        normalLoadN,
        driveForceN,
        brakeForceN,
        gripCoefficient,
        corneringStiffnessNPerMps,
      });

      const totalForce = contactNormal
        .clone()
        .multiplyScalar(normalLoadN)
        .addScaledVector(wheelForward, tire.longitudinalForceN)
        .addScaledVector(wheelRight, tire.lateralForceN);
      this.body.addForceAtPoint(toRapierVector(totalForce), toRapierVector(contactPoint), true);

      wheel.telemetry = {
        ...wheel.telemetry,
        contact: true,
        suspensionLengthM,
        normalLoadN,
        longitudinalVelocityMps,
        lateralVelocityMps,
        longitudinalForceN: tire.longitudinalForceN,
        lateralForceN: tire.lateralForceN,
        slipAngleRad: tire.slipAngleRad,
        gripCoefficient,
      };
    }

    if (horizontalSpeed > 0.001) {
      const resistanceScale =
        this.config.linearResistanceNPerMps +
        this.config.aeroResistanceNPerMpsSquared * horizontalSpeed;
      this.body.addForce(
        {
          x: -linearVelocity.x * resistanceScale,
          y: 0,
          z: -linearVelocity.z * resistanceScale,
        },
        true,
      );
    }
  }

  localPosition(): VehicleLocalPosition {
    const position = this.body.translation();
    return { x: position.x, y: position.y, z: position.z };
  }

  telemetry(): VehicleTelemetry {
    const velocity = this.body.linvel();
    const angularVelocity = this.body.angvel();
    const wheels = this.wheels.map((wheel) => ({ ...wheel.telemetry }));
    const rearWheels = wheels.filter((wheel) => wheel.axle === 'rear');
    return {
      speedMps: Math.hypot(velocity.x, velocity.z),
      steeringAngleRad: this.steeringAngleRad,
      yawRateRadPerSec: angularVelocity.y,
      contactCount: wheels.filter((wheel) => wheel.contact).length,
      maxAbsSlipAngleRad: wheels.reduce(
        (maximum, wheel) => Math.max(maximum, Math.abs(wheel.slipAngleRad)),
        0,
      ),
      rearMaxAbsSlipAngleRad: rearWheels.reduce(
        (maximum, wheel) => Math.max(maximum, Math.abs(wheel.slipAngleRad)),
        0,
      ),
      handbrakeActive: this.handbrakeActive,
      wheels,
    };
  }

  syncVisual(object: THREE.Object3D): void {
    const position = this.body.translation();
    const rotation = this.body.rotation();
    object.position.set(position.x, position.y, position.z);
    object.quaternion.set(rotation.x, rotation.y, rotation.z, rotation.w);
  }

  clearForces(): void {
    this.body.resetForces(true);
    this.body.resetTorques(true);
  }

  rebase(shift: { x: number; y: number }): void {
    if (shift.x === 0 && shift.y === 0) return;
    const position = this.body.translation();
    this.body.setTranslation(
      { x: position.x - shift.x, y: position.y, z: position.z - shift.y },
      true,
    );
    this.physics.world.propagateModifiedBodyPositionsToColliders();
  }

  reset(position: { x: number; z: number; y?: number }, yawRad = 0): void {
    const rotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), yawRad);
    this.body.setTranslation(
      { x: position.x, y: position.y ?? this.config.spawnHeightM, z: position.z },
      true,
    );
    this.body.setRotation(
      { x: rotation.x, y: rotation.y, z: rotation.z, w: rotation.w },
      true,
    );
    this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    this.clearForces();
    for (const wheel of this.wheels) {
      wheel.lastSuspensionLengthM = this.config.suspensionRestLengthM;
    }
    this.physics.world.propagateModifiedBodyPositionsToColliders();
  }

  dispose(): void {
    this.physics.world.removeRigidBody(this.body);
  }
}
