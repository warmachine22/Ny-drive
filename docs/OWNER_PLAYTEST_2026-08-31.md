# Owner playtest direction — 2026-08-31

This note records product-shaping feedback from the first owner desktop playtest and maps it to Roach work so the intent is not lost when agents change.

## Observed issues and task ownership

- **Steering direction was reversed.** Codex corrected this in T015 and added regression coverage. Do not re-open unless a new regression appears.
- **Camera presentation was too close and did not read like the intended miniature/isometric driving game.** T016 corrects this. The visual reference is the elevated, wide, fixed-world presentation of *Smashy Road: Wanted*: the car should remain readable but the player should see enough surrounding street grid and upcoming intersections to choose a turn before reaching it.
- **Prototype handling understeers heavily and right-angle NYC turns require too much slowing.** T008 owns handling balance after T016 so tuning is judged through the intended camera.
- **Handbrake effect is too weak.** T008 owns rear-wheel handbrake braking/grip reduction and controllable physics-driven oversteer.
- **Leaving Roadbed geometry can drop the car into an endless dark void.** T017 owns bounded non-road support plus automatic safe-road recovery. T010 later owns true elevation/grade-separated terrain behavior, so prototype support must remain replaceable rather than silently flattening tunnels/overpasses.
- **A minimap and location context would make real NYC exploration substantially easier.** T018 owns a compact minimap generated from already-streamed centerlines plus current/nearest street name and road-class context (street/avenue/boulevard/highway/ramp/etc.) where source data supports it.

T014 release-style validation now depends on T016/T017/T018 so these owner-visible requirements cannot be omitted from final validation.

## Camera reference observations

Reference: *Smashy Road: Wanted* gameplay imagery and description.

- MobyGames describes the game as using an isometric-like camera in a large open world: https://www.mobygames.com/game/75551/smashy-road-wanted/
- Current gameplay screenshots show the vehicle occupying a modest portion of the frame with substantially more world context than the original Ny-drive T009 camera.
- *Smashy Road: Wanted 2* screenshots also demonstrate a compact upper-left minimap that communicates nearby road choices without dominating the driving view.

For Ny-drive this is a **presentation reference, not a request to copy art or gameplay systems**. NYC geometry remains one-to-one and source-derived; only the readable miniature/isometric framing is being adopted.

The T009 camera used a 34 m vertical orthographic view and a 45° projected-world yaw. On the real Manhattan fixture that yaw nearly counteracted Manhattan's rotated street grid, causing avenues/cross streets to project close to screen vertical/horizontal. T016 rotates the fixed-world camera so the dominant Manhattan directions read as opposing diagonals and raises the elevation angle for a more top-down miniature view. The first 88 m browser capture proved the angle but made the car smaller than the visual reference; T016 therefore uses a tighter balanced baseline while preserving a wider speed-dependent preview.

## Handling reference observations

These are conceptual references only; Ny-drive keeps its Rapier rigid-body + custom four-ray wheel implementation.

### Raycast RC Car

https://github.com/icurtis1/raycast-vehicle

Useful patterns:

- raycast suspension with independently tunable wheel behavior;
- exact static trimesh world collision;
- speed-responsive camera framing;
- live tuning of engine, steering, brakes, suspension, tires, chassis and assists.

### ArcadeCarPhysics

https://github.com/SergeyMakeev/ArcadeCarPhysics

Useful concepts to evaluate in T008:

- speed-dependent steering rather than a single steering ratio;
- Ackermann-style steering geometry/inside-outside wheel angle differences;
- normalized/tunable lateral tire friction;
- stabilizer forces and bounded downforce/assists;
- explicit handbrake behavior.

### Ny-drive tuning rule

Drift must remain the result of forces applied to the dynamic chassis. We may tune speed-dependent steering, front/rear grip balance, lateral slip response, rear handbrake brake/grip, stabilizing/downforce forces and other bounded assists, but must not add a scripted "drift state" that directly rotates or translates the car.

## Retest checklist

After T016/T008/T017/T018, owner/browser playtesting should specifically check:

1. left/right steering remains correct;
2. camera feels like a wide miniature/isometric driving game and gives enough turn preview;
3. normal NYC right-angle turns are achievable without extreme understeer;
4. handbrake clearly initiates/tightens rear rotation at useful speeds;
5. countersteer/throttle can recover a slide;
6. a small road departure does not become an endless fall;
7. minimap communicates nearby connections;
8. street/road name and class give meaningful NYC location context.
