# testing__C109749__NRS-484B-223-3c__motor_vehicle_driver

Status: partial exact case construction. No physical recording has been made or accepted.

Exact law: NRS 484B.223(3)(c) — If a highway has been designed to provide a single center lane to be used only for turning by traffic moving in both directions, the following rules apply: A vehicle must not travel more than 50 feet in a center turn lane after making a left-hand turn onto the highway before merging with traffic.
Assigned branch(es): Intersection entry with receiving traffic.
Cell: C109749 (intersection, left_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Exact coverage and CPU construction

The selected branch has four planned cases in `case-plan.json`: `__below_50ft` (49-foot target), `__at_50ft` (50-foot target), `__above_50ft` (51-foot target), and `__no_merge` (censored observation). The first three form the numeric boundary comparison; below and no-merge form the merge-observation comparison. All require the same verified public highway, single bidirectional exclusive center turn lane, left turn onto that highway, receiving through lane and other vehicle. A commanded merge station is not a measured distance or legal outcome. There are no frozen accepted recordings for this assignment.

`center_lane_site.py::validate_site` requires a reviewed public-highway source, original Native map source, exactly one exclusive bidirectional shared center turn lane, opposing through directions and correct entry/merge targets. `center_lane_measurement.py::measure_center_lane_distance` integrates original body-centre path after the turn completion marker through the first through-lane merge marker. It rejects missing context, missing/duplicated frames, untracked lane exit and duplicate turn events. A missing merge is censored. The raw body history must remain available for reviewer resolution of vehicle reference point and event convention.

`turn_merge_controller.py::TurnMergeController` commands the entry, center-lane and through-lane waypoint route without importing CARLA until `apply`. Fake-vehicle tests exercise eastbound and westbound turns, merge-waypoint progression, steering, speed control and control application. The route must be built from an original source-gated Native site; commands are not observed travel.

`comparison_audit.py` independently checks all three original numeric measurements and the censored no-merge contrast, requiring shared site, receiving traffic, entry route and camera bindings. Negative fixture tests reject missing original traces, changed traffic, censored numeric cases and false no-merge markers.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109749__NRS-484B-223-3c__motor_vehicle_driver/tests -v` passed 23 source-shaped fixture checks in `cpu-construction-tests.log` (SHA256 `f658534224ee7c3f507c95347907b940f6c306d12e5e72a7bc795cff00c4aa79`). These fixtures exercise software geometry and numeric boundaries; they are not original Native measurements.

## Next CPU actions

1. Source-gate a Native map site: original lane topology must establish the single exclusive bidirectional center turn lane and a through-lane merge; review a public-highway source. The exported cell label alone does not establish these facts.
2. Integrate the controller with the exact CARLA runner and four-camera capture, original sample acquisition and saved finalizer. Keep the four target cases and source-bound reference convention; verify both road approach directions.
3. Complete exact semantic proposals, offline and positive/negative compatibility receipts, saved-only processing, delivery/comparison audits, and risk-based fallback only after a measurable physical risk has a tested alternative.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing CPU gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed again with the pinned CPU environment, FFmpeg and Lean. The 23 assignment fixture tests passed. These are construction checks, not delivery proofs. CARLA is needed only after the CPU package is ready for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Current acceptance gate

The assignment-scoped static checkpoint command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete` passed. The same command with `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log`. Status remains partial while listed CPU deliverables are incomplete.
