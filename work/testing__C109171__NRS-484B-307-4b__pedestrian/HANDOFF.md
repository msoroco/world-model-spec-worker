# testing__C109171__NRS-484B-307-4b__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(4)(b) — Where the signal is a green turn arrow alone: Pedestrians facing such a signal shall not enter the highway until permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): Facing arrow before highway entry.
Cell: C109171 (intersection, enter_road, turn_arrow); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109171__NRS-484B-307-4b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
