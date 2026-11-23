# testing__C109705__NRS-484B-400-2a__motor_vehicle_driver

Status: partial source-bound construction draft. Four accepted recording IDs are
retained as reuse candidates pending original-source review; no new recording
is proposed by this checkpoint.

## 2026-11-23 construction checkpoint

The case plan now names all four existing accepted exact case IDs, reuses their
recording IDs as candidates for **source review**, and binds them into
`approach_lateral_position` and `imaginary_approach_lateral_position`. It does
not request duplicate capture or treat accepted membership as proof of the law.
Each comparison holds two-directional intersection geometry, left turn, camera
plan, duration and controller fixed within its pair; the measured approach
body offset is the deliberate difference. The marked versus imaginary
centerline constructions are separate comparisons. There is no numeric legal
cutoff or verdict. The frozen judgment-range file has no range for this law
and actor in full-test.

`construction.py` prepares all four case variants from a source-hashed Native
map survey: marked or imaginary centerline, approach and departure road IDs,
opposed permitted lane directions on both roads, left-turn waypoint route,
vehicle blueprint, spawn offset and a bounded waypoint controller. The 1.7 m
and 2.7 m target offsets are engineering settings. An original map survey is
required before physical dispatch; the module rejects missing or mismatched
geometry. It has not run CARLA.

`approach.py` requires original Native acquisition hashes for
`intersection-context.json` and `approach-history.jsonl`, verifies consecutive
20 Hz frames, measures every pre-entry full-body footprint relative to the
oriented centerline and right-half road edge, and rejects comparisons with
changed fixed conditions or reused original sources. Six focused CPU tests
passed with `.venv-cpu/bin/python -m unittest discover -s
work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/tests -v`;
the exact hashed log is `cpu-approach-tests.log` in result.json. Assignment
`--complete` static check passed. Exact
`.venv-cpu/bin/python worker_check.py --assignment
testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete
--require-delivery-ready` still rejects the partial package with
`Preparation acceptance failed: partial/missing packages remain`.

Next CPU work: obtain or construct a source-hashed Native map survey and exact
runner for the four planned cases; add saved-only finalization and source-bound
diagnostic recipes, offline and compatibility receipts, semantic proposals,
independent delivery audit proofs, and original-recording source review. If the
archived original trace/video confirms complete coverage, retire new capture
plans; if it does not, use the documented gap to prepare new exact captures.
The original archives are not present in this export, so physical coverage,
public highway status and legal nearest-portion judgment remain unresolved.

Exact law: NRS 484B.400(2)(a) — If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: The approach for a left turn must be made in that portion of the right half of the highway nearest the centerline thereof.
Assigned branch(es): Two-directional intersection constructed within the general intersection layout..
Cell: C109705 (intersection, left_turn, centerline); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 4. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
