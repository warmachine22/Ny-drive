import { describe, expect, it } from 'vitest';
import { ackermannWheelSteerAngle, speedSteeringScale } from './Steering';

describe('vehicle steering helpers', () => {
  it('keeps full steering in city-speed turns and reduces it smoothly at high speed', () => {
    const config = { fullStrengthBelowMps: 8, highSpeedMps: 45, minimumScale: 0.5 };
    expect(speedSteeringScale(0, config)).toBeCloseTo(1);
    expect(speedSteeringScale(8, config)).toBeCloseTo(1);
    expect(speedSteeringScale(20, config)).toBeGreaterThan(0.8);
    expect(speedSteeringScale(45, config)).toBeCloseTo(0.5);
    expect(speedSteeringScale(80, config)).toBeCloseTo(0.5);
  });

  it('turns the inside front wheel more sharply while preserving turn sign', () => {
    const leftInside = ackermannWheelSteerAngle(0.5, 2.52, 1.46, -0.73);
    const leftOutside = ackermannWheelSteerAngle(0.5, 2.52, 1.46, 0.73);
    expect(leftInside).toBeGreaterThan(leftOutside);
    expect(leftOutside).toBeGreaterThan(0);

    const rightInside = ackermannWheelSteerAngle(-0.5, 2.52, 1.46, 0.73);
    const rightOutside = ackermannWheelSteerAngle(-0.5, 2.52, 1.46, -0.73);
    expect(Math.abs(rightInside)).toBeGreaterThan(Math.abs(rightOutside));
    expect(rightInside).toBeLessThan(0);
    expect(rightOutside).toBeLessThan(0);
  });
});
