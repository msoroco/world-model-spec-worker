# testing__C147331__NRS-484B-587-2a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.587(2)(a); with 484B.587(3), NRS 484B.210(4) — Except if required by an emergency or as otherwise authorized by subsection 3 [(3) appended below], a person shall not drive a vehicle on a controlled-access highway: Upon any portion of the highway that lies outside of a marked traffic lane or marked entrance or exit lane. A person driving a vehicle described in paragraphs (a) to (f), inclusive, of subsection 4 of NRS 484B.210 [list appended below] may drive that vehicle on a paved shoulder of a controlled-access highway where lawfully placed signage allows that vehicle to use the shoulder in that manner. The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to: (a) An authorized emergency vehicle described in NRS 484A.480; (b) A vehicle which has been issued a permit to operate as an authorized emergency vehicle pursuant to NRS 484A.490; (c) A traffic incident management vehicle; (d) A tow car; (e) A coroner vehicle; or (f) A public transit motor bus, that is being driven on the paved shoulder of a highway where lawfully placed signage allows that vehicle to use the shoulder in that manner.
Assigned branch(es): Outside-lane travel beside one-way marked lanes.
Cell: C147331 (one_way_multilane, travel, lane_marking); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147331__NRS-484B-587-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
