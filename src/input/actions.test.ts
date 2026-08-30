import { describe, expect, it } from 'vitest';
import { actionForKey, DrivingInputState } from './actions';

describe('driving action mapping', () => {
  it('maps required keyboard controls to semantic actions', () => {
    expect(actionForKey('KeyA')).toBe('steerLeft');
    expect(actionForKey('KeyD')).toBe('steerRight');
    expect(actionForKey('KeyW')).toBe('throttle');
    expect(actionForKey('KeyS')).toBe('brakeReverse');
    expect(actionForKey('Space')).toBe('handbrake');
    expect(actionForKey('KeyR')).toBe('reset');
  });

  it('produces a normalized driving snapshot', () => {
    const state = new DrivingInputState();
    state.set('steerLeft', true);
    state.set('throttle', true);
    state.set('handbrake', true);

    expect(state.snapshot()).toEqual({
      steer: -1,
      throttle: 1,
      brakeReverse: 0,
      handbrake: true,
      reset: false,
    });

    state.clear();
    expect(state.snapshot().steer).toBe(0);
  });
});
