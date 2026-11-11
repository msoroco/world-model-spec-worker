# heldout__C110779__NRS-484B-113-1__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.113(1) — The driver of a vehicle: Shall not back the vehicle unless such movement can be made with reasonable safety and without interfering with other traffic.
- Cell/actor: C110779 / motor_vehicle_driver; layout `intersection`, maneuver `reverse`, control `other_vehicle`.
- Exact input: `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/assignment.json` (SHA256 `cea1a7b04dc28362442d4962618eb853bcf512afc0cb0496bfe7d17b194c20f1`).
- Witness: `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/witnesses.json`, source index 61; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.backing, drv.time_to_conflict, rel.surface_gap, drv.hard_deceleration, ru.pedestrian, rel.bearing, rel.contact.

## Required source and construction review

1. Establish eligible vehicle and driver attribution and supported reverse control.
2. Highway-use facts and observation of all relevant traffic, surrounding objects and responses.
3. Intersection backing corridor with proposed onset, course and end.
4. Observe all relevant traffic, surrounding objects, clearances, responses, and contact throughout backing.
5. Preserve drv.backing, drv.time_to_conflict, rel.surface_gap, drv.hard_deceleration, ru.pedestrian, rel.bearing, and rel.contact as observations.
6. Qualifying motor vehicle and driver in actual physical control.
7. Reasonable safety and interference remain uninterpreted; no conflict-time, braking, or contact rule is supplied.
8. Separate other vehicle with specified position, motion, purpose and relationship to the backing corridor.
9. Specify proposed backing, actual onset, course, end, and intersection corridor.
10. Specify the other vehicle's position, motion, travel purpose, highway use, and relationship to the backing route.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C110779__NRS-484B-113-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.
