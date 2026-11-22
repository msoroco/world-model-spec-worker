# testing__C149237__NRS-484B-127-2__heavy_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.127(2) — The driver of any truck or combination of vehicles 80 inches or more in overall width, which is following a truck, or combination of vehicles 80 inches or more in overall width, shall, whenever conditions permit, leave a space of 500 feet so that an overtaking vehicle may enter and occupy such space without danger, but this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles. This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.
Assigned branch(es): Qualifying truck following.
Cell: C149237 (one_way_road, follow, truck); actor: heavy_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 3. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 19. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 19 exact law/actor ranges. These are unmeasured construction targets. 6 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
