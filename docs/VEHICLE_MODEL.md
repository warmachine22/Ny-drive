# Vehicle Model

Ny-drive's first vehicle simulation is an original, unbranded late-1990s AWD rally-sedan prototype intended to establish the handling architecture before exact model-year data or licensed art is selected.

## Simulation contract

- Rapier owns one dynamic chassis rigid body. The car is never moved kinematically during ordinary driving.
- Rendering follows the Rapier body; the procedural body/wheel mesh has no third-party branded assets.
- Four wheel hardpoints cast suspension rays along chassis-local down. Queries exclude the player's own rigid body and chassis collider.
- Suspension is spring/damper force applied at each contact point.
- Tire forces are calculated in each wheel's forward/right basis and applied at the contact point, so steering and weight movement produce chassis torque naturally.
- Longitudinal and lateral tire demand share a combined load-dependent grip limit. The current curve uses smooth saturation rather than a binary grip switch so T008 can tune the grip-to-slide transition without replacing the model.
- AWD torque split is data-driven. The starting prototype uses a mild rear bias rather than claiming an exact historical Subaru center-differential specification.
- Physics runs at a fixed 120 Hz target through an accumulator independent of render frame rate. Catch-up work is bounded to avoid a long frame causing an unbounded physics spiral.

## Starting parameters

The values in `src/vehicle/VehicleConfig.ts` are prototype tuning values, not asserted factory specifications. Important starting dimensions are approximately 1230 kg mass, 2.52 m wheelbase, 1.46 m track, and 0.30 m wheel radius. Springs, dampers, grip, inertia, steering, drive force, brake force, and AWD split remain configurable.

T013 owns the final distributable asset/licensing strategy. Reliable vehicle research can refine dimensions and drivetrain parameters later without changing the subsystem boundaries.

## World interaction rules

T006 established that the streamed NYC Roadbed polygon mesh is the collision authority and that one static Rapier trimesh exists per physics-active tile. T007 must not run suspension/drive substeps unless the player's current global tile is `active-physics`.

Rapier world-level scene queries use an acceleration structure that is brought current through the normal world update path. After inserting or floating-origin-translating standalone road colliders, the runtime performs a fixed physics refresh before suspension rays resume. This is intentionally explicit because T006 tests found that assuming immediate world-query visibility is incorrect.

The current Manhattan fixture is flat. T007 therefore validates stability, steering/braking/acceleration, and tile-seam traversal on flat Roadbed geometry. T010 owns elevation, slopes, bridges, tunnels, and multi-level road structures; uneven-grade vehicle validation belongs there and in final T014 verification.

## Telemetry

The vehicle exposes:

- horizontal speed;
- steering angle;
- wheel contact count;
- per-wheel suspension length and normal load;
- per-wheel longitudinal/lateral contact velocity and force;
- per-wheel slip angle and maximum absolute slip angle.

This telemetry is intentionally lightweight but sufficient for T008 handling/drift tuning and later performance/debug overlays.

## Deferred behavior

T007 does not attempt final drift feel, handbrake behavior, camera feel, safe-road reset selection, gearing/turbo simulation, differential sophistication, damage, or branded presentation. T009 adds the actual follow-camera/reset experience; T008 then tunes drift/handbrake behavior through that camera. Keeping those tasks separate prevents subjective tuning from being baked into the basic rigid-body implementation.
