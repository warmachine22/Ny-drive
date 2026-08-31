export interface FixedStepResult {
  steps: number;
  alpha: number;
  droppedSeconds: number;
}

export class FixedStepRunner {
  private accumulatorSeconds = 0;

  constructor(
    readonly fixedDeltaSeconds = 1 / 120,
    readonly maxSubSteps = 8,
  ) {
    if (!(fixedDeltaSeconds > 0)) throw new Error('fixedDeltaSeconds must be positive.');
    if (!Number.isInteger(maxSubSteps) || maxSubSteps < 1) {
      throw new Error('maxSubSteps must be a positive integer.');
    }
  }

  advance(frameDeltaSeconds: number, step: (deltaSeconds: number) => void): FixedStepResult {
    const safeFrameDelta = Number.isFinite(frameDeltaSeconds)
      ? Math.max(0, frameDeltaSeconds)
      : 0;
    this.accumulatorSeconds += safeFrameDelta;

    let steps = 0;
    while (this.accumulatorSeconds >= this.fixedDeltaSeconds && steps < this.maxSubSteps) {
      step(this.fixedDeltaSeconds);
      this.accumulatorSeconds -= this.fixedDeltaSeconds;
      steps += 1;
    }

    let droppedSeconds = 0;
    if (this.accumulatorSeconds >= this.fixedDeltaSeconds) {
      droppedSeconds =
        this.accumulatorSeconds - (this.accumulatorSeconds % this.fixedDeltaSeconds);
      this.accumulatorSeconds %= this.fixedDeltaSeconds;
    }

    return {
      steps,
      alpha: this.accumulatorSeconds / this.fixedDeltaSeconds,
      droppedSeconds,
    };
  }

  reset(): void {
    this.accumulatorSeconds = 0;
  }
}
