export type VehicleAxle = 'front' | 'rear';

export interface VehicleConfig {
  massKg: number;
  centerOfMassY: number;
  principalInertiaKgM2: { x: number; y: number; z: number };
  chassisHalfExtentsM: { x: number; y: number; z: number };
  wheelbaseM: number;
  trackM: number;
  suspensionMountY: number;
  suspensionRestLengthM: number;
  suspensionTravelM: number;
  wheelRadiusM: number;
  springRateNPerM: number;
  damperRateNsPerM: number;
  maxSuspensionForceN: number;
  maxSteerRad: number;
  maxDriveForceN: number;
  maxReverseForceN: number;
  maxBrakeForceN: number;
  awdFrontBias: number;
  tireGripCoefficient: number;
  frontGripScale: number;
  rearGripScale: number;
  corneringStiffnessNPerMps: number;
  frontCorneringScale: number;
  rearCorneringScale: number;
  handbrakeRearBrakeForceN: number;
  handbrakeRearGripScale: number;
  handbrakeRearCorneringScale: number;
  handbrakeRearDriveScale: number;
  handbrakeSlideStartMps: number;
  handbrakeSlideFullMps: number;
  linearResistanceNPerMps: number;
  aeroResistanceNPerMpsSquared: number;
  linearDamping: number;
  angularDamping: number;
  spawnHeightM: number;
}

export const GC8_PROTOTYPE_CONFIG: Readonly<VehicleConfig> = {
  massKg: 1230,
  centerOfMassY: -0.18,
  principalInertiaKgM2: { x: 1900, y: 2200, z: 420 },
  chassisHalfExtentsM: { x: 0.84, y: 0.29, z: 2.08 },
  wheelbaseM: 2.52,
  trackM: 1.46,
  suspensionMountY: -0.12,
  suspensionRestLengthM: 0.34,
  suspensionTravelM: 0.16,
  wheelRadiusM: 0.30,
  springRateNPerM: 36000,
  damperRateNsPerM: 4200,
  maxSuspensionForceN: 12000,
  maxSteerRad: 0.52,
  maxDriveForceN: 9000,
  maxReverseForceN: 5000,
  maxBrakeForceN: 14000,
  awdFrontBias: 0.45,
  tireGripCoefficient: 1.12,
  frontGripScale: 1,
  rearGripScale: 0.99,
  corneringStiffnessNPerMps: 2200,
  frontCorneringScale: 1,
  rearCorneringScale: 0.98,
  handbrakeRearBrakeForceN: 7000,
  handbrakeRearGripScale: 0.62,
  handbrakeRearCorneringScale: 0.55,
  handbrakeRearDriveScale: 0.2,
  handbrakeSlideStartMps: 3,
  handbrakeSlideFullMps: 12,
  linearResistanceNPerMps: 18,
  aeroResistanceNPerMpsSquared: 0.42,
  linearDamping: 0.05,
  angularDamping: 0.22,
  spawnHeightM: 0.72,
};
