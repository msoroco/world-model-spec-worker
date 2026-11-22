# testing__C272352__NRS-484B-270-2b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(2)(b) — When overtaking or passing a bicycle, an electric bicycle or an electric scooter proceeding in the same direction, the driver of a motor vehicle shall exercise due care and: If there is only one lane for traffic proceeding in the same direction, pass to the left of the bicycle, electric bicycle or electric scooter at a safe distance, which must be not less than 3 feet between any portion of the vehicle and the bicycle, electric bicycle or electric scooter, and shall not move again to the right side of the highway until the vehicle is safely clear of the overtaken bicycle, electric bicycle or electric scooter. Except as otherwise provided in NRS 484B.213 and 484B.217 [NRS-484B-213-1, NRS-484B-213-2a, NRS-484B-213-2b, NRS-484B-213-2c, NRS-484B-217-2], when passing to the left of a bicycle, electric bicycle or electric scooter at a safe distance of not less than 3 feet between any portion of the vehicle and the bicycle, electric bicycle or electric scooter, this paragraph authorizes the driver, if it is safe, to pass: (1) To the left of the center of the highway. (2) In a no-passing zone.
Assigned branch(es): Single-lane left passing, clearance and return-right ordering.
Cell: C272352 (single_lane_per_direction, overtake_left, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C272352__NRS-484B-270-2b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
