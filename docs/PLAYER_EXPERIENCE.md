# Player Experience Runtime

This document records the first free-driving camera, input, spawn, and reset contracts. It is intentionally about subsystem behavior rather than final visual tuning; T008 owns drift/handbrake feel and T014 owns release-style browser validation.

## Input boundary

Vehicle physics consumes semantic `DrivingInputSnapshot` values only. Keyboard DOM events remain in `src/input`.

Continuous actions (`steer`, `throttle`, `brake/reverse`, `handbrake`) remain active while held. `reset` is edge-triggered: the action state emits one reset pulse when R changes from released to pressed, then remains false until R is released and pressed again. This prevents one key hold from resetting the vehicle every render frame.

## Near-isometric follow camera

`src/camera/IsometricFollowCamera.ts` uses an orthographic Three.js camera with a fixed world-space yaw and pitch. It follows the dynamic vehicle position but deliberately does **not** inherit chassis yaw, roll, or pitch, which keeps the miniature/isometric presentation readable during rapid vehicle rotation.

The camera:

- exponentially smooths the followed position;
- adds velocity-based look-ahead so more of the approaching street is visible at speed;
- clamps look-ahead so a transient velocity spike cannot throw the framing far away;
- zooms out modestly as speed rises;
- applies the exact same floating-origin X/Z shift as the vehicle and loaded world, preventing a rebase from appearing as a giant camera pan.

T008 may tune camera constants together with handling observations, but it should not turn the camera into a vehicle-yaw-locked chase camera unless product intent changes.

## Safe road pose

Spawn/reset selection is driven by compiled world data rather than arbitrary scene coordinates.

`src/world/RoadPose.ts` searches loaded centerline paths, projects the requested global point onto the nearest segment, and returns that position plus a heading aligned with the road. Reverse-direction centerlines invert the segment heading. Centerline geometry is preferred because it gives a credible lane-independent road axis; when no centerline is available, the code falls back to an interior candidate derived from the Roadbed polygon.

This is a runtime recovery heuristic, not a replacement for map topology. Future grade-separated reset logic must account for road level/elevation once T010 adds vertical geometry.

## Reset flow

A reset is asynchronous and pauses vehicle substeps while recovery is in progress:

1. finish any already-running stream update;
2. update/load around the car's current global X/Z location;
3. choose the nearest loaded safe road pose, falling back to the initial spawn pose when necessary;
4. move the floating origin to that global pose and apply the same rebase to vehicle, streamer, and camera;
5. ensure the destination road tile is physics-active;
6. run the established Rapier world-query refresh step;
7. reset the dynamic chassis to local `(0, spawnHeight, 0)` with the road heading, zero velocity, and reset suspension state;
8. snap the camera's internal focus to the recovered vehicle pose and resume fixed-step simulation.

No page reload or mission/game-state reset is required.

## Asynchronous streaming and floating origin

T007 review identified a race in the earlier interface: `WorldStreamer.update(player, runtimeOrigin)` could begin a tile load, the game could rebase while that load was in flight, and the eventual attachment could still use the old `runtimeOrigin` captured at update start.

T009 fixes this inside `WorldStreamer`. The streamer keeps the current runtime origin as mutable subsystem state. `rebase(shift)` updates that state immediately; after asynchronous loading completes, attachment reads the current origin. The regression test starts a delayed tile load, rebases before resolving it, then proves the tile is attached against the rebased origin.

This keeps the correctness rule local to the streaming subsystem rather than requiring every caller to perfectly serialize network/disk completion with floating-origin movement.

## Verification boundary

Automated tests cover:

- reset one-shot semantics;
- camera smoothing, bounded look-ahead, speed zoom, fixed isometric offset, and origin rebasing;
- centerline safe-pose projection/heading plus Roadbed fallback;
- asynchronous tile completion after floating-origin rebase;
- all existing streaming, collision, vehicle, tire, and fixed-step tests.

Subjective camera readability and driving feel still require a real browser interaction pass. T008 should record those observations while tuning drift/handbrake behavior; T014 will add the final browser smoke/performance gate.
