# testing__C109749__NRS-484B-253__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.253 — The driver of a vehicle within an intersection intending to turn to the left shall yield the right-of-way to any vehicle approaching from the opposite direction which is within the intersection or so close thereto as to constitute an immediate hazard, but such driver, having so yielded and having given a signal when and as required, may make such left turn and the drivers of all other vehicles approaching the intersection from the opposite direction shall yield the right-of-way to the vehicle making the left turn.
Assigned branch(es): Initial yield duty; opposing vehicle within intersection..
Cell: C109749 (intersection, left_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 6. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 8. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 8 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
