# heldout__C230671__NRS-484B-403-1__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.403(1) — A U-turn may be made on any road where the turn can be made with safety, except as prohibited by this section [NRS-484B-403-2, NRS-484B-403-3] and by the provisions of NRS 484B.227, 484B.363 and 484B.407 [NRS-484B-227-1, NRS-484B-363-3, NRS-484B-407].
- Cell/actor: C230671 / motor_vehicle_driver; layout `road`, maneuver `u_turn`, control `other_vehicle`.
- Exact input: `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/assignment.json` (SHA256 `834dd810ea6cd5332d5adf243bf6ee56e31cd839347bcb0d2da2b553507f9086`).
- Witness: `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.u_turn, st.roadway, drv.time_to_conflict, rel.oncoming, drv.following, st.sight_distance, kin.speed, drv.hard_deceleration.

## Required source and construction review

1. All incorporated prohibition conditions.
2. Establish public vehicular use, highway boundaries and location outside city territorial limits.
3. Identify the driver in actual physical control and qualifying vehicle.
4. Other vehicle's actual route, position, speed and motion relative to the reversal.
5. Preserve the unresolved safety standard and obtain the full incorporated prohibition texts before determining their applicability.
6. Qualifying road and conventional motor vehicle with an identified driver in physical control.
7. Realizable turning envelope and observations throughout constituent movements.
8. Supply a realizable reversal path, surrounding vehicle trajectories, visibility and observations throughout all constituent movements.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C230671__NRS-484B-403-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.
