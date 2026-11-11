# heldout__C111610__NRS-484B-413-1__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.413(1) — A driver shall not turn a vehicle from a direct course upon a highway unless and until such movement can be made with reasonable safety, and then only after giving a clearly audible signal by sounding the horn if any pedestrian may be affected by such movement and after giving an appropriate signal if any other vehicle may be affected by such movement.
- Cell/actor: C111610 / motor_vehicle_driver; layout `intersection`, maneuver `turn`, control `pedestrian`.
- Exact input: `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/assignment.json` (SHA256 `c0c7db22fa23340f1dcbf392684a9481578d6ab648dbed7f6e49fc145fb5cdc7`).
- Witness: `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.turning, drv.lane_change, drv.time_to_conflict, ru.pedestrian, sig.horn, sig.turn_indicator, sig.hand_signal, drv.following, rel.surface_gap.

## Required source and construction review

1. Construct the direct approach, turn route, pedestrian route and intersection governance.
2. Establish driver physical control, an ordinary motor vehicle and highway status.
3. Establish highway status, qualifying vehicle and actual driver control.
4. For an emitted-horn example, provide actual emission and received acoustic evidence at the pedestrian, including timing and ambient conditions; a command alone is insufficient.
5. Preserve reasonable safety, possible effect and clearly audible as unresolved standards.
6. Provide actual horn emission and received acoustic evidence at the pedestrian, including timing and ambient conditions.
7. Specify the direct approach, turn, pedestrian route and intersection governance.
8. Use a person afoot and retain their position and motion relative to the turn.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C111610__NRS-484B-413-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.
