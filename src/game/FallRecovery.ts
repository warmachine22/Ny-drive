export const DEFAULT_FALL_RECOVERY_DROP_M = 5;

export class FallRecoveryMonitor {
  private latched = false;

  constructor(readonly dropBelowSurfaceM = DEFAULT_FALL_RECOVERY_DROP_M) {}

  update(positionY: number, referenceSurfaceY = 0): boolean {
    const lost =
      !Number.isFinite(positionY) ||
      !Number.isFinite(referenceSurfaceY) ||
      positionY < referenceSurfaceY - this.dropBelowSurfaceM;
    if (!lost) {
      this.latched = false;
      return false;
    }
    if (this.latched) return false;
    this.latched = true;
    return true;
  }

  reset(): void {
    this.latched = false;
  }
}
