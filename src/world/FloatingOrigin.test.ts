import { FloatingOrigin } from './FloatingOrigin';

describe('FloatingOrigin', () => {
  it('preserves geographic identity across a rebase', () => {
    const origin = new FloatingOrigin({ x: 1000, y: 3200 }, 500);
    const before = origin.globalFromLocal({ x: 620, z: -80 });
    const result = origin.rebaseIfNeeded({ x: 620, z: -80 });
    expect(result).not.toBeNull();
    const after = origin.globalFromLocal(result?.local ?? { x: NaN, z: NaN });
    expect(after).toEqual(before);
    expect(result?.shift).toEqual({ x: 620, y: -80 });
  });

  it('does not rebase while local coordinates are small', () => {
    const origin = new FloatingOrigin({ x: 1000, y: 3200 }, 500);
    expect(origin.rebaseIfNeeded({ x: 120, z: 80 })).toBeNull();
  });
});
