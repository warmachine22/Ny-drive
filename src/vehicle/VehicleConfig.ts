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
  fullSteerBelowMps: number;
  highSpeedSteerMps: number;
  minimumSteerScale: number;
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
  // T007's 0.52 rad plus aggressive linear high-speed reduction felt strongly
  // understeery in the first owner playtest. Keep useful city-speed steering authority,
  // then smoothly reduce it as speed rises rather than clipping turn-in early.
  maxSteerRad: 0.62,
  fullSteerBelowMps: 8,
  highSpeedSteerMps: 45,
  minimumSteerScale: 0.5,
  maxDriveForceN: 9000,
  maxReverseForceN: 5000,
  maxBrakeForceN: 14000,
  awdFrontBias: 0.43,
  tireGripCoefficient: 1.10,
  frontGripScale: 1.08,
  rearGripScale: 0.97,
  corneringStiffnessNPerMps: 2250,
  frontCorneringScale: 1.10,
  rearCorneringScale: 0.96,
  // The handbrake is deliberately rear-specific. It removes most rear drive,
  // adds meaningful rear brake demand and blends down rear lateral authority only
  // after the car is moving, allowing a physically driven rotation without a drift state.
  handbrakeRearBrakeForceN: 9000,
  handbrakeRearGripScale: 0.46,
  handbrakeRearCorneringScale: 0.40,
  handbrakeRearDriveScale: 0.05,
  handbrakeSlideStartMps: 2.5,
  handbrakeSlideFullMps: 10,
  linearResistanceNPerMps: 18,
  aeroResistanceNPerMpsSquared: 0.42,
  linearDamping: 0.05,
  angularDamping: 0.20,
  spawnHeightM: 0.72,
};
