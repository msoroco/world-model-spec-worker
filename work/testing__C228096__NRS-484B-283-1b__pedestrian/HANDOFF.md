# testing__C228096__NRS-484B-283-1b__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(b) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: A pedestrian shall not suddenly leave a curb or other place of safety and walk or run into the path of a vehicle which is so close that it is impossible for the driver to yield.
Assigned branch(es): Road entry from curb into vehicle path..
Cell: C228096 (road, enter_road, other_vehicle); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__NRS-484B-283-1b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
