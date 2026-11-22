# testing__C230223__NRS-484B-270-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(3) — The driver of a motor vehicle shall yield the right-of-way to any person riding a bicycle, an electric bicycle or an electric scooter or a pedestrian as provided in subsection 6 of NRS 484B.297 [NRS-484B-297-6] on the pathway or lane. The driver of a motor vehicle shall not enter, stop, stand, park or drive within a pathway or lane provided for bicycles, electric bicycles or electric scooters except: (a) When entering or exiting an alley or driveway; (b) When operating or parking a disabled vehicle; (c) To avoid conflict with other traffic; (d) In the performance of official duties; (e) In compliance with the directions of a police officer; or (f) In an emergency.
Assigned branch(es): Yield interaction with a bicycle rider on the designated lane.
Cell: C230223 (road, travel, cycle_lane); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230223__NRS-484B-270-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
