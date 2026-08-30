type RapierModule = typeof import('@dimforge/rapier3d-compat');
type RapierApi = RapierModule['default'];
type RapierWorld = InstanceType<RapierApi['World']>;

export interface GravityVector {
  x: number;
  y: number;
  z: number;
}

export interface PhysicsRuntime {
  readonly world: RapierWorld;
  step(deltaSeconds: number): void;
  dispose(): void;
}

let rapierPromise: Promise<RapierApi> | undefined;

async function loadRapier(): Promise<RapierApi> {
  if (!rapierPromise) {
    rapierPromise = import('@dimforge/rapier3d-compat').then(async ({ default: rapier }) => {
      await rapier.init();
      return rapier;
    });
  }
  return rapierPromise;
}

class RapierPhysicsRuntime implements PhysicsRuntime {
  constructor(readonly world: RapierWorld) {}

  step(deltaSeconds: number): void {
    this.world.timestep = Math.max(1 / 240, Math.min(deltaSeconds, 1 / 20));
    this.world.step();
  }

  dispose(): void {
    this.world.free();
  }
}

export async function createPhysicsRuntime(
  gravity: GravityVector = { x: 0, y: -9.81, z: 0 },
): Promise<PhysicsRuntime> {
  const rapier = await loadRapier();
  return new RapierPhysicsRuntime(new rapier.World(gravity));
}
