import * as THREE from 'three';

export interface CameraMotionState {
  position: { x: number; y: number; z: number };
  velocity: { x: number; y: number; z: number };
}

export interface IsometricCameraConfig {
  yawRad: number;
  pitchRad: number;
  distanceM: number;
  responsePerSecond: number;
  lookAheadSeconds: number;
  maxLookAheadM: number;
  baseZoom: number;
  highSpeedZoom: number;
  highSpeedMps: number;
}

export interface IsometricCameraDebugState {
  focus: { x: number; y: number; z: number };
  lookAhead: { x: number; y: number; z: number };
  zoom: number;
}

export const DEFAULT_ISOMETRIC_CAMERA: Readonly<IsometricCameraConfig> = {
  yawRad: Math.PI / 4,
  pitchRad: Math.PI / 4,
  distanceM: 31,
  responsePerSecond: 5.5,
  lookAheadSeconds: 0.55,
  maxLookAheadM: 8,
  baseZoom: 1,
  highSpeedZoom: 0.82,
  highSpeedMps: 35,
};

function smoothingAlpha(responsePerSecond: number, deltaSeconds: number): number {
  return 1 - Math.exp(-Math.max(0, responsePerSecond) * Math.max(0, deltaSeconds));
}

function clampVectorLength(vector: THREE.Vector3, maxLength: number): THREE.Vector3 {
  const length = vector.length();
  if (length > maxLength && length > 0) vector.multiplyScalar(maxLength / length);
  return vector;
}

export class IsometricFollowCamera {
  private readonly focus = new THREE.Vector3();
  private readonly smoothedLookAhead = new THREE.Vector3();
  private initialized = false;

  constructor(
    private readonly camera: THREE.OrthographicCamera,
    readonly config: Readonly<IsometricCameraConfig> = DEFAULT_ISOMETRIC_CAMERA,
  ) {
    this.camera.up.set(0, 1, 0);
  }

  reset(state: CameraMotionState): void {
    this.focus.set(state.position.x, state.position.y, state.position.z);
    this.smoothedLookAhead.copy(this.targetLookAhead(state.velocity));
    this.initialized = true;
    this.applyCamera(state.velocity);
  }

  update(state: CameraMotionState, deltaSeconds: number): void {
    if (!this.initialized) {
      this.reset(state);
      return;
    }

    const alpha = smoothingAlpha(this.config.responsePerSecond, deltaSeconds);
    const target = new THREE.Vector3(state.position.x, state.position.y, state.position.z);
    const lookAhead = this.targetLookAhead(state.velocity);
    this.focus.lerp(target, alpha);
    this.smoothedLookAhead.lerp(lookAhead, alpha);
    this.applyCamera(state.velocity);
  }

  rebase(shift: { x: number; y: number }): void {
    if (!this.initialized || (shift.x === 0 && shift.y === 0)) return;
    this.focus.x -= shift.x;
    this.focus.z -= shift.y;
    this.camera.position.x -= shift.x;
    this.camera.position.z -= shift.y;
  }

  debugState(): IsometricCameraDebugState {
    return {
      focus: { x: this.focus.x, y: this.focus.y, z: this.focus.z },
      lookAhead: {
        x: this.smoothedLookAhead.x,
        y: this.smoothedLookAhead.y,
        z: this.smoothedLookAhead.z,
      },
      zoom: this.camera.zoom,
    };
  }

  private targetLookAhead(velocity: CameraMotionState['velocity']): THREE.Vector3 {
    const lookAhead = new THREE.Vector3(velocity.x, 0, velocity.z)
      .multiplyScalar(this.config.lookAheadSeconds);
    return clampVectorLength(lookAhead, this.config.maxLookAheadM);
  }

  private applyCamera(velocity: CameraMotionState['velocity']): void {
    const target = this.focus.clone().add(this.smoothedLookAhead);
    const horizontalDistance = this.config.distanceM * Math.cos(this.config.pitchRad);
    const offset = new THREE.Vector3(
      Math.cos(this.config.yawRad) * horizontalDistance,
      Math.sin(this.config.pitchRad) * this.config.distanceM,
      Math.sin(this.config.yawRad) * horizontalDistance,
    );
    this.camera.position.copy(target).add(offset);
    this.camera.lookAt(target);

    const speedMps = Math.hypot(velocity.x, velocity.z);
    const speedRatio = Math.min(1, speedMps / Math.max(0.1, this.config.highSpeedMps));
    const targetZoom = THREE.MathUtils.lerp(
      this.config.baseZoom,
      this.config.highSpeedZoom,
      speedRatio,
    );
    this.camera.zoom = THREE.MathUtils.lerp(this.camera.zoom, targetZoom, 0.18);
    this.camera.updateProjectionMatrix();
  }
}
