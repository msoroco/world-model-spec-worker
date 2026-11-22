# testing__C380107__NRS-484B-208-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.208(1); with 484B.208(2) — Except as otherwise provided in subsection 2, on a controlled-access highway which has two or more clearly marked lanes for traveling in the same direction, a driver may not continue to operate a motor vehicle in the extreme left lane if the driver knows, or reasonably should know, that he or she is traveling at a rate of speed which is less than the posted speed limit for that portion of the controlled-access highway and is being overtaken in that lane from the rear by a motor vehicle traveling at a higher rate of speed. The requirements of subsection 1 do not apply: (a) To a driver operating a motor vehicle that is: (1) Overtaking another vehicle proceeding in the same direction; (2) Preparing for a left turn at an intersection; (3) Traveling in a lane designated for the use of high-occupancy vehicles pursuant to NRS 484A.460, if the driver complies with the requirements to travel in such a lane [DEF-NRS-484A-460-2, NRS-484B-323-1]; or (4) Engaged in the construction, maintenance or repair of the highway, including, without limitation, the removal of snow. (b) When traffic conditions, inclement weather, obstructions or hazards make it necessary to drive in the extreme left lane. (c) When compliance with an official traffic control device or the directions given by a peace officer makes it necessary to drive in the extreme left lane. (d) To the driver of an authorized emergency vehicle in the course of his or her official duties. (e) To a driver operating a motor vehicle within the geographical limits of a city or town.
Assigned branch(es): Core encounter with qualified HOV exception.
Cell: C380107 (controlled_access_multilane, travel, hov_lane); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C380107__NRS-484B-208-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
