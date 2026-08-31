import { describe, expect, it } from 'vitest';
import { FallRecoveryMonitor } from './FallRecovery';

describe('FallRecoveryMonitor', () => {
  it('triggers once after dropping below the nearby driving surface', () => {
    const monitor = new FallRecoveryMonitor(5);
    expect(monitor.update(0, 0)).toBe(false);
    expect(monitor.update(-4.9, 0)).toBe(false);
    expect(monitor.update(-5.1, 0)).toBe(true);
    expect(monitor.update(-20, 0)).toBe(false);
    expect(monitor.update(0.5, 0)).toBe(false);
    expect(monitor.update(-8, 0)).toBe(true);
  });

  it('does not mistake a legitimate below-grade tunnel for an infinite fall', () => {
    const monitor = new FallRecoveryMonitor(5);
    expect(monitor.update(-12, -10)).toBe(false);
    expect(monitor.update(-14.9, -10)).toBe(false);
    expect(monitor.update(-15.1, -10)).toBe(true);
  });

  it('treats non-finite heights as unrecoverable and can be explicitly reset', () => {
    const monitor = new FallRecoveryMonitor(5);
    expect(monitor.update(Number.NaN, -10)).toBe(true);
    expect(monitor.update(Number.NaN, -10)).toBe(false);
    monitor.reset();
    expect(monitor.update(Number.POSITIVE_INFINITY, -10)).toBe(true);
  });
});
