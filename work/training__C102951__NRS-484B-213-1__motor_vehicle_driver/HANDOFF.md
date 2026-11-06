# training__C102951__NRS-484B-213-1__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.213(1): A vehicle must not be driven to the left side of the center of a two-lane, two-directional highway and overtaking and passing another vehicle proceeding in the same direction, unless such left side is clearly visible and is free of oncoming traffic for a sufficient distance ahead to permit such overtaking and passing to be completely made without interfering with the safe operation of any vehicle approaching from the opposite direction or any vehicle overtaken.

Cell: hill_crest / overtake_left / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

two-lane two-way road; same-direction overtaken vehicle; crest geometry fixed; left-of-center passing attempt Vary only `measured_clear_oncoming_distance` (m) across [70, 120, 170]. Measure roadway sight distance, oncoming trajectories, pass completion and interference over the full pass. The definitions are not selected recordings, and requested settings are not measured results.

## Exact-source review and observation repair

The frozen `assignment.json` quotes NRS 484B.213(1), and frozen witness 76 cites the allowance for a clearly visible left side free of oncoming traffic for sufficient distance. The witness is a low-confidence, unverified proposal, not execution evidence. The operative text also requires an actual left-of-center overtake of a same-direction vehicle on a two-lane two-directional highway, complete passing before the clear distance expires, and no interference with either an approaching or an overtaken vehicle. Topic IDs `text-0` and `reviewed-scope-0` remain draft coverage targets.

The prior observation draft routed every proposed term through `measured_clear_oncoming_distance`. That single scalar cannot establish highway geometry, actual left-of-center occupation, visibility from the driver's eye at the crest, pass completion, or the separate responses of approaching and overtaken vehicles. `case-plan.json` now names mandatory proposed channels for those facts and maps each source observation term to the relevant channels. In particular, approaching and overtaken response channels are distinct. No numeric threshold for statutory “sufficient distance” or “safe operation” is asserted; any declared operational model must preserve the underlying measurements for independent judgment.

This repair is a source review and capture specification only. No Native emitter, camera/trace join, Core mapping, saved processor, exact four-candidate construction, offline check, portable compatibility receipt, or independent audit exists. The package remains blocked and unselected; physical visibility and interference remain later CARLA observations.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Sufficient distance and safe operation remain unresolved judgments; visibility from actual ego eye and crest occluder needed. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
