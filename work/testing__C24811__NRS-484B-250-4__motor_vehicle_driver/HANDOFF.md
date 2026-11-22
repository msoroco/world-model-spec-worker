# testing__C24811__NRS-484B-250-4__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.250(4) — When a vehicle enters an intersection controlled by a traffic-control signal which is installed and has its vehicular signals uncovered, but is inoperative at the time the vehicle enters the intersection, the driver of the vehicle shall proceed as if a stop sign had been erected at each entrance to the intersection and shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After making such a stop, the driver shall proceed cautiously, yielding to vehicles which have previously completed a stop or are within the intersection.
Assigned branch(es): Blind-intersection post-stop interactions under complete signal inoperability..
Cell: C24811 (blind_intersection, travel, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
