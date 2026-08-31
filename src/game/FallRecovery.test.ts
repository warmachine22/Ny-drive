import { describe, expect, it } from 'vitest';
import { FallRecoveryMonitor } from './FallRecovery';

describe('FallRecoveryMonitor', () => {
  it('triggers once below the safety threshold until the vehicle returns to a valid height', () => {
    const monitor = new FallRecoveryMonitor(-5);
    expect(monitor.update(0)).toBe(false);
    expect(monitor.update(-4.9)).toBe(false);
    expect(monitor.update(-5.1)).toBe(true);
    expect(monitor.update(-20)).toBe(false);
    expect(monitor.update(0.5)).toBe(false);
    expect(monitor.update(-8)).toBe(true);
  });

  it('treats non-finite height as unrecoverable and can be explicitly reset', () => {
    const monitor = new FallRecoveryMonitor(-5);
    expect(monitor.update(Number.NaN)).toBe(true);
    expect(monitor.update(Number.NaN)).toBe(false);
    monitor.reset();
    expect(monitor.update(Number.POSITIVE_INFINITY)).toBe(true);
  });
});
