# testing__C149470__LVMC-11-60-030-A4__bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.60.030(A)(4) — The operator of a bus, other than a tour bus, shall: Enter a bus stop, bus stand, passenger loading zone or origin or destination point on a public street in such a manner that the bus when stopped to load or unload passengers or baggage shall be in a position with the right-hand front wheel of such vehicle not farther than eighteen inches from the curb and the bus approximately parallel to the curb so as not to unduly impede the movement of other vehicular traffic.
Assigned branch(es): Right-front-wheel distance at stopped loading.
Cell: C149470 (one_way_road, load_unload, curb); actor: bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C149470__LVMC-11-60-030-A4__bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
