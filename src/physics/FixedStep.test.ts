import { describe, expect, it } from 'vitest';
import { FixedStepRunner } from './FixedStep';

describe('FixedStepRunner', () => {
  it('decouples simulation cadence from render-frame cadence', () => {
    const runner = new FixedStepRunner(1 / 120, 8);
    const steps: number[] = [];

    const first = runner.advance(1 / 60, (delta) => steps.push(delta));
    expect(first.steps).toBe(2);
    expect(steps).toEqual([1 / 120, 1 / 120]);

    const second = runner.advance(1 / 240, (delta) => steps.push(delta));
    expect(second.steps).toBe(0);
    const third = runner.advance(1 / 240, (delta) => steps.push(delta));
    expect(third.steps).toBe(1);
    expect(steps.every((delta) => delta === 1 / 120)).toBe(true);
  });

  it('bounds catch-up work after a long frame', () => {
    const runner = new FixedStepRunner(1 / 120, 4);
    const result = runner.advance(1, () => undefined);
    expect(result.steps).toBe(4);
    expect(result.droppedSeconds).toBeGreaterThan(0);
    expect(result.alpha).toBeGreaterThanOrEqual(0);
    expect(result.alpha).toBeLessThan(1);
  });
});
