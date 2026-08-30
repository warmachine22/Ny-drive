import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from './PhysicsWorld';

describe('physics runtime boundary', () => {
  it('initializes Rapier and advances a world behind the wrapper', async () => {
    const runtime = await createPhysicsRuntime();
    expect(runtime.world.gravity.y).toBeCloseTo(-9.81, 2);
    runtime.step(1 / 60);
    runtime.dispose();
  });
});
