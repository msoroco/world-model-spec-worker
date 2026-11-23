# testing__C104081__NRS-484B-297-6__pedestrian

Status: partial CPU construction and comparison-audit checkpoint. The strict assignment gate remains open; no physical or legal acceptance is claimed.

Exact law: NRS 484B.297(6) — A pedestrian walking or otherwise traveling on a sidewalk who encounters an obstruction to his or her mobility on the sidewalk, including, without limitation, a short section of the sidewalk that is missing or impassable, may proceed with due care on the immediately adjacent highway to move around such an obstruction. Such a pedestrian: (a) Must walk or otherwise travel as far to the side of the highway near the sidewalk as possible; (b) May walk or otherwise travel on the highway in the direction he or she was walking or traveling on the sidewalk, regardless of the direction of traffic; (c) May walk or otherwise travel in a lane provided for bicycles, electric bicycles or electric scooters if the area between the lane and the sidewalk is impassable; and (d) Must return to the sidewalk as soon as practicable.
Assigned branch(es): Adjacent designated-lane bypass with intervening-area physical variations..
Cell: C104081 (hill_crest, travel, obstruction); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Current constructed plan

`case-plan.json` now specifies five exact cases: `__clear_intervening`, `__blocked_intervening`, `__blocked_opposite`, `__blocked_late_return`, and `__missing_sidewalk`, each prefixed by this assignment ID. It specifies four controlled comparisons: intervening-area condition, travel direction, sidewalk-return opportunity, and sidewalk-obstruction type. Every case carries source gap IDs and a physical-risk assessment. Frozen `evidence.json` has zero accepted recordings, so source-backed reuse is unavailable. No judgment range entry matches this law and actor, and no numeric legal cutoff is assumed.

`geometry.py` constructs distinct sidewalk, intervening area, designated bicycle lane and adjacent highway rectangles, an actual sidewalk obstruction, optional intervening barrier, and pedestrian routes in both longitudinal directions. Its design audit samples each path and rejects obstacle intersection, missing barriers, misaligned boundaries and wrong lane use. The coordinates are local engineering metres awaiting surveyed CARLA map binding; no physical feasibility is asserted.

`comparison_audit.py` independently requires original saved-acquisition packets and matching SHA-256 values. It rejects missing cases, synthetic-source labels, changed fixed conditions and undeclared differences. It reports source consistency only; due care, far-to-side, impassability and as-soon-as-practicable remain unresolved judgments.

`native_construction.py` now requires a SHA-bound original Native map survey naming the exact C104081 hill-crest map, sidewalk, intervening area, designated bicycle lane, adjacent highway and local-to-world transform before any actor creation. It calls explicit adapter methods to spawn the pedestrian, sidewalk obstruction and optional intervening barrier, set the route and read back the created resources. The missing-sidewalk variant requires a surveyed existing surface gap and never substitutes a fake obstacle. A route-control or readback failure destroys owned handles in reverse order. No actual site survey or CARLA adapter has been bound; these CPU spy tests prove call order and rejection behavior only.

## Next CPU actions

1. Bind the authored cross section to a surveyed Native sidewalk/highway/bicycle-lane map; implement the CARLA adapter, capture, world snapshot/restore and finalization.
2. Author source-bound measurement contracts and positive/negative compatibility receipts for all exact cases, canonical semantic proposals, saved-only processing and the independent delivery audit. Wire `comparison_audit.py` to original measured packets.
3. Review the exact law and clause alternatives independently, then repair any missing cases or comparisons. Keep all judgments unresolved pending source evidence.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C104081__NRS-484B-297-6__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`cpu-preflight.log`: `.venv-cpu/bin/python runtime.py preflight` passed. `cpu-tests.log`: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C104081__NRS-484B-297-6__pedestrian/tests -v` passed 21 tests, including negative geometry, survey, actor cleanup and source-audit branches. `cpu-static-check.log`: the assignment `worker_check.py --complete` passed. `cpu-strict-gate.log`: exact assignment `--complete --require-delivery-ready` failed because the status is correctly partial. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
