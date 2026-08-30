import type { RuntimeOrigin, WorldPoint } from './types';

export interface LocalPoint {
  x: number;
  z: number;
}

export interface RebaseResult {
  shift: WorldPoint;
  local: LocalPoint;
}

export class FloatingOrigin {
  private currentOrigin: RuntimeOrigin;

  constructor(
    initialOrigin: RuntimeOrigin = { x: 0, y: 0 },
    private readonly thresholdM = 512,
  ) {
    this.currentOrigin = { ...initialOrigin };
  }

  get origin(): RuntimeOrigin {
    return { ...this.currentOrigin };
  }

  globalFromLocal(local: LocalPoint): WorldPoint {
    return {
      x: this.currentOrigin.x + local.x,
      y: this.currentOrigin.y + local.z,
    };
  }

  localFromGlobal(global: WorldPoint): LocalPoint {
    return {
      x: global.x - this.currentOrigin.x,
      z: global.y - this.currentOrigin.y,
    };
  }

  setOrigin(next: RuntimeOrigin): WorldPoint {
    const shift = {
      x: next.x - this.currentOrigin.x,
      y: next.y - this.currentOrigin.y,
    };
    this.currentOrigin = { ...next };
    return shift;
  }

  rebaseIfNeeded(local: LocalPoint): RebaseResult | null {
    if (Math.hypot(local.x, local.z) < this.thresholdM) {
      return null;
    }
    const shift = { x: local.x, y: local.z };
    this.currentOrigin = {
      x: this.currentOrigin.x + shift.x,
      y: this.currentOrigin.y + shift.y,
    };
    return { shift, local: { x: 0, z: 0 } };
  }
}
