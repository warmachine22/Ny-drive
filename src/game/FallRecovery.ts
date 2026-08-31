export const DEFAULT_FALL_RECOVERY_Y_M = -5;

export class FallRecoveryMonitor {
  private latched = false;

  constructor(readonly thresholdY = DEFAULT_FALL_RECOVERY_Y_M) {}

  update(positionY: number): boolean {
    const lost = !Number.isFinite(positionY) || positionY < this.thresholdY;
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
