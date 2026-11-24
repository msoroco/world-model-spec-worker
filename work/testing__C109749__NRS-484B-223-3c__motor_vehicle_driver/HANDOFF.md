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

`native_capture.py::capture_original` now writes a source-bound original 20 Hz body/lane/event trace, four-camera frame map with each original camera file SHA256, site packet and measured capture receipt. It requires reviewed highway and Native map source hashes, original contiguous frame/time identity, a single observed turn event and observed merge lane; it rejects drift, missing camera/lane readbacks, camera source byte tampering and duplicate capture. The saved delivery audit can consume this receipt directly. These tests use fixture readbacks, so source review and physical observation remain pending.

`delivery_audit.py::audit_saved_delivery` independently reopens and hashes the original trace, highway review, lane-design packet and 20 Hz frame map; it joins every original trace frame to all four camera source names and recomputes the delivered turn/merge frames and distance. Its read-only CPU tests reject a tampered trace, substituted result arithmetic, changed context source, missing camera, missing frame and path escape. This is a saved-source audit implementation, not a positive compatibility receipt or physical acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109749__NRS-484B-223-3c__motor_vehicle_driver/tests -v` passed 34 source-shaped fixture checks in `cpu-construction-tests.log` (SHA256 `df33241fbc469f6b16fe278e111e1c9aea5c3261bddaf128ce41e89e2652d9fe`). These fixtures exercise software geometry, numeric boundaries and source integrity; they are not original Native measurements.

## Next CPU actions

1. Source-gate a Native map site: original lane topology must establish the single exclusive bidirectional center turn lane and a through-lane merge; review a public-highway source. The exported cell label alone does not establish these facts.
2. Integrate the controller and new Native acquisition bridge with the exact CARLA runner and actual four-camera sensor files, then complete a saved finalizer. Keep the four target cases and source-bound reference convention; verify both road approach directions.
3. Wire the read-only delivery audit to the case-specific saved finalizer and original Native acquisition files; complete exact semantic proposals, offline and positive/negative compatibility receipts, saved-only processing and risk-based fallback only after a measurable physical risk has a tested alternative.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing CPU gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed again with the pinned CPU environment, FFmpeg and Lean. The 34 assignment fixture tests passed. These are construction and saved-source audit checks, not exact delivery proofs. CARLA is needed only after the CPU package is ready for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Current acceptance gate

The assignment-scoped static checkpoint command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete` passed. The same command with `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log`. Status remains partial while listed CPU deliverables are incomplete.
