# testing__C110264__NRS-484B-210-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.210(1); with 484B.210(4) — The driver of a vehicle may overtake and pass upon the right of another vehicle only under the following conditions: (a) When the driver of the vehicle overtaken is making or signaling to make a left turn. (b) Upon a highway with unobstructed pavement which is not occupied by parked vehicles and which is of sufficient width for two or more lines of moving vehicles in each direction. (c) Upon a highway with unobstructed pavement which is not marked as a traffic lane and which is not occupied by parked vehicles, if the vehicle that is overtaking and passing another vehicle: (1) Except as otherwise provided in subsection 4 [(4) appended below], does not travel more than 200 feet in the section of pavement not marked as a traffic lane; or (2) While being driven in the section of pavement not marked as a traffic lane, does not travel through an intersection or past any private way that is used to enter or exit the highway. (d) Upon any highway on which traffic is restricted to one direction of movement, where the highway is free from obstructions and of sufficient width for two or more lines of moving vehicles. The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to: (a) An authorized emergency vehicle described in NRS 484A.480; (b) A vehicle which has been issued a permit to operate as an authorized emergency vehicle pursuant to NRS 484A.490; (c) A traffic incident management vehicle; (d) A tow car; (e) A coroner vehicle; or (f) A public transit motor bus, that is being driven on the paved shoulder of a highway where lawfully placed signage allows that vehicle to use the shoulder in that manner.
Assigned branch(es): Paragraph (a) near an intersection.
Cell: C110264 (intersection, overtake_right, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110264__NRS-484B-210-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
