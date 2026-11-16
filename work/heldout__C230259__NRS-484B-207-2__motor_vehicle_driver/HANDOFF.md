# heldout__C230259__NRS-484B-207-2__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.207(2) — Except when overtaking and passing on the right is permitted, the driver of an overtaken vehicle shall give way to the right in favor of the overtaking vehicle upon observing the overtaking vehicle or hearing a signal. The driver of an overtaken vehicle shall not increase the speed of the vehicle until completely passed by the overtaking vehicle.
- Cell/actor: C230259 / motor_vehicle_driver; layout `road`, maneuver `travel`, control `other_vehicle`.
- Exact input: `inputs/heldout__C230259__NRS-484B-207-2__motor_vehicle_driver/assignment.json` (SHA256 `8c527426a04c528d922afbe17ed7f75ea7ad18bffc0057c8180380fe23e37e72`).
- Witness: `inputs/heldout__C230259__NRS-484B-207-2__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.overtaking, rel.visible, rel.ahead_behind_in_lane, rel.bearing, kin.speed, kin.accel_longitudinal, rel.occupies, sig.horn, drv.passing_side.

## Required source and construction review

1. Construct relative trajectories, passing side and continuous ego speed and lateral-motion histories.
2. Establish the overtaken ego's driver and both vehicle classifications.
3. For giving way, establish actual observation or hearing rather than merely visibility or signal emission.
4. For the give-way sentence, establish actual observation or hearing and retain the permitted-right-passing exception separately.
5. Identify ego's driver, included vehicle classifications and a separate faster overtaking vehicle.
6. Preserve 'completely passed' without choosing a clearance threshold.
7. Preserve unresolved law governing permitted right passing and confine that exception to the give-way sentence.
8. Specify relative positions, motion, passing side, purpose and roadway geometry.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C230259__NRS-484B-207-2__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C230259__NRS-484B-207-2__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

### 2026-11-15 worker-owned source-shaped measurement checkpoint

Read the exact NRS 484B.207(2) text and the C230259 road/travel/other_vehicle cell. `case-plan.json` now has six exact planned cases and four comparisons: rightward response, observed versus signaled notice, speed changes before/after full-body pass completion, and a separately sourced permitted-right-pass premise. The right-pass exception attaches only to the give-way sentence; no legal permission is inferred from a physical passing-side flag. No accepted recordings are listed, and the evidence review names four exact gaps. Subjective observation/hearing remains unconfirmed by mere line of sight, horn emission or fixture audio.

`overtake_geometry.py` is a pure source-shaped original-frame measurement module for a later Native finalizer. It requires distinct actor IDs, four original corners for each body, original 20 Hz frame identity and a near-unit source-surveyed local road tangent. It retains per-frame rear-of-overtaker to front-of-ego clearance, lateral passing side, ego right projection and both speeds; reports the first full-body pass-completion bracket, maximum right displacement, overall and pairwise precompletion speed increases, and recurrence of body overlap. It returns no observation/hearing, permission, physical completion or legal finding. Four CPU tests cover full-body bracket, right/left passing, a speed increase after an earlier decrease, and rejection of missing body, broken sample timing or changed actor identity. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C230259__NRS-484B-207-2__motor_vehicle_driver/tests -v` exits 0; `cpu-tests.log` SHA-256 `a8d510bc7609e4984d2da5e8bac571e832a59c953e530670ead3e7f519f24652`. Assignment-scoped nonstrict `worker_check.py --complete` passes. Status remains **partial**.

Next worker-owned CPU work: build the first exact Native runner and source-hashed four-camera/acoustic capture, connect original participant and ego frames to `overtake_geometry.py` in a saved finalizer, separately source the right-pass permission premise, and run exact offline, positive/missing-source compatibility and fresh-original saved-only processing before expanding the remaining cases/fallbacks. Then complete canonical semantic stages, physical/lifecycle and independent delivery/comparison audits and the scoped strict gate. No GPU or legal acceptance is claimed, and missing code is not an external blocker.
