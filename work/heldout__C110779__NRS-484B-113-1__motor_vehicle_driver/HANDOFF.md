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

## 2026-11-11 backing source measurement checkpoint

The frozen accepted-evidence inventory contains zero recordings. `case-plan.json` now plans six exact cases and five controlled comparisons for wider/narrower traffic clearance, observed other-vehicle braking, contact, pedestrian proximity and a forward-only activation control. All exact cases remain unconstructed; the conditional witness remains only a planning lead.

`backing_safety_measurement.py` joins original 20 Hz ego and surrounding-user motion to original contact packets, with independently cited actor position, motion, purpose and highway use. It measures negative longitudinal ego speed relative to actual heading, the continuous backing interval, participant surface gaps and relative bearings, participant acceleration during backing, and contact frames during backing. A forward-only trace returns a null backing interval for the activation control. A backing interval with an interruption is rejected for separate review. Reasonable safety and interference judgments remain null; no gap, braking or contact cutoff is treated as law. Native source acquisition, actual other-vehicle purpose, four cameras and saved finalizer remain CPU work.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `57b007d9ed610f0eb62a59bd93915c811343fae28526b476261efa74e5fbbc9a`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `524ec85fd5f2cf8f482fe7a8d31d29c36faf6d1a097f41ff990479d464e1efec`). They check measured reverse geometry/contact and reject uncited traffic context, frame mismatch, changed actor IDs, missing original contact source and interrupted backing. These fixtures do not establish physical safety or traffic interference.

Next CPU work: construct a primary Native backing corridor with reverse control and a separately motivated other vehicle, acquire source packets and four cameras, add the saved finalizer, and run exact offline, positive/negative compatibility and saved processing. Then implement the linked cases, risk-based fallbacks, semantic proposals and independent audits. Keep `result.json` partial until its scoped strict gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C110779__NRS-484B-113-1__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result remains partial (`strict-gate.log`).
