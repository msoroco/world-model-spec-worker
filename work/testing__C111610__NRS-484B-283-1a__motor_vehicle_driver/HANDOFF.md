# testing__C111610__NRS-484B-283-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(a); with 484B.283(4) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: When official traffic-control devices are not in place or not in operation, the driver of a vehicle shall yield the right-of-way, slowing down or stopping if need be so to yield, to a pedestrian crossing the highway within a crosswalk when the pedestrian is upon the half of the highway upon which the vehicle is traveling or onto which the vehicle is turning, or when the pedestrian is approaching so closely from the opposite half of the highway as to be in danger. As used in this section, “half of the highway” means all traffic lanes of a highway which are designated for traffic traveling in one direction, and includes the entire highway in the case of a one-way highway.
Assigned branch(es): Pedestrian on the half onto which ego turns..
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
