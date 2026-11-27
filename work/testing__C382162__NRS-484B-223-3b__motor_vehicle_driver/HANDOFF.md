# testing__C382162__NRS-484B-223-3b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.223(3)(b) — If a highway has been designed to provide a single center lane to be used only for turning by traffic moving in both directions, the following rules apply: A vehicle must not travel more than 200 feet in a center turn lane before making a left-hand turn from the highway.
Assigned branch(es): Intersection departure from the center lane.
Cell: C382162 (intersection, left_turn, center_turn_lane); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C382162__NRS-484B-223-3b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 distance construction checkpoint

Four exact source-bound cases now cover nominal 190, 200 and 210 feet before left turn from the highway, plus a 210-foot left-turn-onto-highway applicability contrast. Two comparisons hold shared-lane design, vehicle, camera and measurement method fixed. Nominal engineering targets are neither original measurements nor legal verdicts. `center_lane_distance_probe.py` measures 20 Hz original-frame body occupancy and path length only after source-bound highway/lane design and a connected left-turn departure; it rejects interrupted occupancy, wrong route, missing source/time joins and contradictory body readbacks. `measure_exact` joins the reviewed original OpenDRIVE/highway packet and keeps the left-turn-onto-highway contrast outside the exact distance restriction. `center_lane_geometry.py` computes original eight-vertex body overlap and full containment against a reviewed lane polygon, including both approach orientations and rejection of separated or nonfinite geometry. `measure_with_original_body` derives occupancy from those source vertices and rejects a conflicting Native occupancy flag. Thirteen focused CPU tests pass (`cpu-distance-probe-tests.log`; SHA256 `1d047345700c3a58af8f6ecc012a1f16956d6b3b9aba020e962131586e275cec`). The adapted `center_lane_site.py` additionally checks original map and reviewed highway source bindings, one exclusive bidirectional center turn lane, opposite through-lane directions, street-intersection classification and the exact from-versus-onto route relationship.

Assignment-scoped static `worker_check.py --complete` passes with the selected plan; this is not delivery readiness. Status remains partial. Next: bind the probe to original Native acquisition and selected construction bundles, then semantic proposals, all exact current-runtime offline and positive/negative compatibility, saved-only, physical/lifecycle, independent delivery and comparison proofs, and the scoped strict gate. Original map/Native/pixel and legal review remain later local checks.
