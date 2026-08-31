# Vehicle Model

Ny-drive's first vehicle simulation is an original, unbranded late-1990s AWD rally-sedan prototype intended to establish the handling architecture before exact model-year data or licensed art is selected.

## Simulation contract

- Rapier owns one dynamic chassis rigid body. The car is never moved kinematically during ordinary driving.
- Rendering follows the Rapier body; the procedural body/wheel mesh has no third-party branded assets.
- Four wheel hardpoints cast suspension rays along chassis-local down. Queries exclude the player's own rigid body and chassis collider.
- Suspension is spring/damper force applied at each contact point.
- Tire forces are calculated in each wheel's forward/right basis and applied at the contact point, so steering and weight movement produce chassis torque naturally.
- Longitudinal and lateral tire demand share a combined load-dependent grip limit. The curve uses smooth saturation rather than a binary grip switch so the transition into slip remains progressive.
- AWD torque split is data-driven. The prototype uses a mild rear bias rather than claiming an exact historical Subaru center-differential specification.
- Physics runs at a fixed 120 Hz target through an accumulator independent of render frame rate. Catch-up work is bounded to avoid a long frame causing an unbounded physics spiral.

## T008 owner-playtest handling pass

The first owner desktop playtest found two clear problems: ordinary turns produced excessive understeer and the handbrake had too little rotational effect. T008 changes the force model without introducing a scripted drift state.

- **Speed-dependent steering:** full steering authority remains available through low/city speeds, then falls smoothly toward a bounded high-speed scale instead of the original aggressive linear reduction.
- **Ackermann front steering:** the inside front wheel receives a slightly larger steering angle than the outside wheel, producing a more credible low/mid-speed turn geometry.
- **Axle balance:** front/rear grip and cornering stiffness have independent data-driven scales. The initial T008 tune gives the front axle modestly greater lateral authority and the rear slightly less, reducing the strong prototype understeer while preserving an AWD feel.
- **Rear-only handbrake:** handbrake input removes most rear drive, adds meaningful rear brake demand, and blends down rear grip/cornering authority with speed. At parking speed the blend remains mild; at useful drift-entry speeds it can initiate or tighten chassis rotation.
- **Physical recovery:** countersteer and throttle act through wheel/tire forces only. There is no drift mode that directly changes chassis yaw, translation, or velocity.

These concepts were informed by open raycast/sim-cade vehicle references documented in `docs/OWNER_PLAYTEST_2026-08-31.md`; no external vehicle code is copied into the runtime.

## Starting parameters

The values in `src/vehicle/VehicleConfig.ts` are prototype tuning values, not asserted factory specifications. Important starting dimensions are approximately 1230 kg mass, 2.52 m wheelbase, 1.46 m track, and 0.30 m wheel radius. Springs, dampers, grip, inertia, steering, drive force, brake force, axle balance and AWD split remain configurable.

T013 owns the final distributable asset/licensing strategy. Reliable vehicle research can refine dimensions and drivetrain parameters later without changing the subsystem boundaries.

## World interaction rules

T006 established that the streamed NYC Roadbed polygon mesh is the collision authority and that one static Rapier trimesh exists per physics-active tile. Vehicle substeps must not run unless the player's current global tile is `active-physics`.

Rapier world-level scene queries use an acceleration structure that is brought current through the normal world update path. After inserting or floating-origin-translating standalone road colliders, the runtime performs a fixed physics refresh before suspension rays resume. This is intentionally explicit because T006 tests found that assuming immediate world-query visibility is incorrect.

The current Manhattan fixture is flat. T010 owns elevation, slopes, bridges, tunnels, and multi-level road structures; uneven-grade vehicle validation belongs there and in final T014 verification.

## Telemetry

The vehicle exposes:

- horizontal speed;
- steering angle and chassis yaw rate;
- wheel contact count;
- handbrake active state;
- per-wheel suspension length and normal load;
- per-wheel longitudinal/lateral contact velocity and force;
- per-wheel slip angle and effective grip coefficient;
- maximum absolute slip plus rear-axle maximum slip.

The HUD surfaces speed, overall/rear slip, yaw rate and handbrake state during the T008 tuning phase. This is lightweight enough to keep for later diagnostics and is useful for browser evidence.

## Automated behavior gates

T008 adds three complementary checks on top of the existing tire/vehicle tests:

1. steering geometry tests cover smooth speed scaling and inside/outside Ackermann angles;
2. a normal city-speed maneuver must generate decisive right-turn yaw/lateral displacement without handbrake while retaining at least three wheel contacts;
3. a handbrake maneuver must reduce rear grip and produce more rear slip/yaw than the same steering maneuver without handbrake, then show lower slip/yaw after handbrake release plus physical countersteer/throttle recovery.

Final subjective feel still requires owner/browser playtesting. These tests protect the physical mechanisms so future tuning does not silently regress into the original understeer/weak-handbrake behavior.
