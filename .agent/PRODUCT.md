# Product

Status: ACCEPTED

This file is the durable, authoritative representation of the owner's intended product. Preserve decisions and intent rather than conversation history.

## Vision

Ny-drive is a browser-based isometric 3D driving sandbox whose defining feature is a one-to-one drivable recreation of New York City's street network across all five boroughs. The roads, intersections, widths, lane structure, grades, bridges, tunnels, and distances should follow real-world geographic data as closely as practical, while the surrounding city is intentionally simplified and procedurally rendered rather than reproduced photorealistically. The initial experience is deliberately focused: one highly enjoyable late-1990s Subaru Impreza WRX STI / GC8-era car, open roads, and physics-driven arcade/simulation handling that makes exploring, sliding, and handbrake drifting through a geographically authentic NYC fun in its own right.

## Goals

- Make the full five-borough NYC road network continuously drivable at real-world scale.
- Prioritize road and intersection accuracy over photorealistic scenery.
- Deliver satisfying physics-based driving with believable weight, suspension, tire slip, AWD behavior, controllable oversteer, and handbrake drifting.
- Keep the initial game focused on free driving with one car and no traffic so world streaming and vehicle feel can be excellent before broader game systems are added.
- Use real geographic source data and an offline map-compilation pipeline so the browser streams only the nearby world instead of loading NYC at once.
- Make recognizable NYC geography enjoyable to explore from an isometric 3D presentation even though individual buildings may be visually simplified.

## Non-Goals

- Photorealistic or one-to-one visual reproduction of every NYC building, storefront, sign, tree, parked car, or street furnishing.
- NPC traffic, pedestrians, police, missions, races, career progression, multiplayer, or an economy in the initial product scope.
- Recreating the entire Earth or cities outside New York City.
- A hardcore motorsport simulator whose realism takes priority over accessible, expressive driving and drifting.
- Interior exploration, walking gameplay, building interiors, or character gameplay.
- Requiring the complete five-borough world to reside in browser memory at the same time.

## Users / Audience

The primary audience is players who enjoy driving, drifting, cars, New York City, real-world maps, and open-ended exploration. The core player should be able to launch the game in a modern desktop browser and immediately understand the experience without needing to learn a large progression system or simulator setup.

## Core Experience

The player launches the game, spawns in New York City in the initial car, and can immediately drive. Streets exist at real-world scale and connect according to the actual NYC network, so familiar trips, neighborhoods, bridges, highways, and cross-borough routes can be driven rather than merely approximated. The camera presents the world from an isometric or near-isometric 3D viewpoint and follows the car smoothly.

Driving should sit between arcade and simulation. Steering, throttle, braking, suspension, tire grip, slip, weight transfer, and AWD traction should matter, but the car should remain forgiving enough that intentional slides and recovery are fun. The handbrake must be a meaningful control for initiating or tightening rotation. When the car becomes stuck or overturned, the player can quickly reset to a safe drivable state.

The world streams around the player. Nearby road, collision, terrain, and scenery tiles are loaded at useful detail; distant or unnecessary geometry is simplified or unloaded. Buildings and environmental massing may use real footprints and approximate heights where useful, but the visual treatment should remain stylized/simple enough to support performance and development scope.

## Design Pillars

1. **The map is the feature.** NYC's road geometry and scale are more important than decorative fidelity.
2. **Driving must feel good before the game becomes large.** Vehicle feel, drift control, camera behavior, and frame consistency take priority over adding systems.
3. **Real geography, simplified presentation.** Use authoritative geographic data where it affects driving; generate or simplify scenery where it does not.
4. **Stream the city, never brute-force it.** Runtime cost should depend mainly on the player's surroundings, not on the total size of NYC.
5. **Open-road simplicity.** The first compelling version should be fun with one car and nothing to do except drive.

## Requirements

- **FR-001**: The game MUST provide a continuously drivable representation of the public road network across Manhattan, Brooklyn, Queens, the Bronx, and Staten Island at one-to-one world scale, subject to the accuracy and licensing limits of the source data.
- **FR-002**: The map pipeline MUST derive road position and driveable roadbed geometry from real NYC/OpenStreetMap geographic data rather than hand-authored fictional street layouts.
- **FR-003**: The road representation MUST preserve meaningful real-world driving attributes where source data supports them, including road width, lane count or lane structure, directionality, intersection shape, and road classification.
- **FR-004**: The world MUST represent elevation/grade and MUST distinguish grade-separated roads such as bridges, elevated roads, tunnels, and overpasses so crossing roads are not incorrectly treated as flat intersections.
- **FR-005**: The runtime MUST stream geographic world tiles around the player and unload or simplify tiles outside the active area rather than loading the complete city into active render and physics memory.
- **FR-006**: The initial playable vehicle MUST be a late-1990s Subaru Impreza WRX STI / GC8-era car, or a legally distributable equivalent representation if exact branded assets cannot be shipped.
- **FR-007**: Vehicle motion MUST be physics-driven and include steering, throttle, braking, suspension/ground contact, tire grip and slip, AWD traction behavior, and vehicle mass/inertia rather than direct kinematic movement.
- **FR-008**: The driving model MUST support intentional controllable oversteer/drifting and a handbrake control that materially changes rear-wheel grip or braking behavior to initiate or tighten rotation.
- **FR-009**: The game MUST provide an isometric or near-isometric 3D follow camera that keeps the car readable at driving speed while preserving a useful view of upcoming streets.
- **FR-010**: The initial world presentation MUST use simplified/procedural scenery rather than requiring photorealistic reproduction; building footprints, heights, terrain, vegetation, and street dressing MAY use real geographic data where it improves recognition at reasonable runtime cost.
- **FR-011**: The initial game mode MUST be free driving on open roads with no required NPC traffic, pedestrians, missions, races, or progression systems.
- **FR-012**: The player MUST have a fast reset/recovery action that returns an overturned, stuck, fallen, or otherwise undrivable vehicle to a safe nearby road state.
- **FR-013**: The game MUST provide desktop-browser driving controls sufficient for steering, throttle, braking/reverse, handbrake, and reset; the implementation SHOULD be structured so additional input devices can be added later.
- **QR-001**: The client MUST run without a native installation in a modern desktop web browser using Three.js-based 3D rendering or a directly compatible successor chosen during technical planning.
- **QR-002**: World coordinates and generated road geometry MUST use a meter-based local coordinate system with no intentional rescaling of NYC distances; source-data uncertainty MUST be preserved as uncertainty rather than hidden by invented precision.
- **QR-003**: Runtime memory and physics workload MUST be bounded primarily by the active streaming radius, not by the total five-borough dataset size.
- **QR-004**: The architecture MUST keep map compilation/data preparation separate from browser runtime rendering and vehicle simulation so the city can be regenerated from source data without manually rebuilding game scenes.
- **QR-005**: The project MUST preserve required attribution and comply with the licenses/terms of every geographic dataset, code dependency, and distributed vehicle/art asset used by the game.

## Constraints

- The primary delivery target is a web browser; a native desktop build is not required for the initial product.
- Three.js is the intended rendering foundation unless planning identifies a strong compatibility reason to use a directly related browser rendering layer.
- NYC is the only geographic scope for the initial product.
- The complete city must be generated/streamed from data rather than manually modeled road by road.
- Official NYC GIS data should be preferred for NYC-specific geometry where it provides better local fidelity; OpenStreetMap and compatible elevation datasets may supplement missing attributes such as lanes, bridges, tunnels, or road hierarchy.
- The first version intentionally limits dynamic world actors to the player's vehicle; static/procedural scenery may be added as needed for spatial readability.
- Exact Subaru branding, logos, and a specific third-party vehicle model cannot be assumed distributable until licensing is resolved; this must not block development of the driving prototype.

## Success Criteria

- A fresh player can open the browser build, spawn a vehicle, steer, accelerate, brake, use the handbrake, drift, recover the car, and continue driving without a mission or tutorial dependency.
- Representative street grids in each borough are generated from geographic source data at one-to-one scale and connect into a continuous citywide road network.
- A player can complete long real-world routes that cross neighborhoods and borough boundaries without a scene reload that breaks the driving experience.
- Complex grade-separated locations can be represented without false flat intersections that make routes physically impossible or incorrect.
- The same map compiler can regenerate road tiles from source data instead of requiring manual scene editing for every neighborhood.
- During ordinary driving, the client loads and simulates only a bounded region around the player and can discard regions left behind.
- The vehicle has a distinct, controllable grip-to-slide transition and the handbrake is useful for deliberate rotation rather than acting only as a conventional stop button.
- The city remains recognizable from its street layout, terrain, block massing, major crossings, and borough-scale geography even when individual buildings are simplified.

## Open Questions

These questions are important but do not block technical planning or an initial prototype:

- Will the eventual public release be commercial, free, or private? This affects data, trademark, music, and vehicle-asset licensing decisions.
- Should the final shipped vehicle use exact Subaru/WRX/STI branding and a licensed GC8 model, or should development retain an unbranded equivalent until rights are resolved?
- Should gamepad support be part of the first public milestone or follow the keyboard-controlled prototype?
- What final visual direction should the procedural city use: clean low-poly, miniature/isometric, muted realistic materials, or another stylized treatment?
- What hardware/performance floor should become the formal launch target after the first representative NYC streaming prototype is profiled?

## Future / Possibilities

The following ideas are intentionally outside current accepted scope and should not automatically generate implementation tasks: traffic, pedestrians, parked vehicles, multiplayer/free-roam convoys, time of day, weather, police, races, missions, route challenges, additional cars, tuning, damage, replays, photo mode, gamepad/wheel features beyond the initial input target, mobile support, and richer landmark-specific art.
