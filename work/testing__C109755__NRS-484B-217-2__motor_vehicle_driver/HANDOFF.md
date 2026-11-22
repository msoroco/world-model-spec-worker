# testing__C109755__NRS-484B-217-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.217(2); with 484B.217(3), 484B.217(4) — Except as otherwise provided in subsections 3 and 4, a driver shall not drive on the left side of the highway within such zone or drive across or on the left side of any pavement striping designed to mark such zone throughout its length. A driver may drive across a pavement striping marking such zone to an adjoining highway if the driver has first given the appropriate turn signal and there will be no impediment to oncoming or following traffic. Except where otherwise provided, a driver may drive across a pavement striping marking such a zone to make a left-hand turn if the driver has first given the appropriate turn signal in compliance with NRS 484B.413 [NRS-484B-413-2], if it is safe and if it would not be an impediment to oncoming or following traffic.
Assigned branch(es): left-hand-turn crossing.
Cell: C109755 (intersection, left_turn, pavement_striping); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109755__NRS-484B-217-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
