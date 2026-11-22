# testing__C135705__NRS-484B-440-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.440(1); with 484B.440(2) — Upon any highway outside of a business or residence district no person shall stop, park or leave standing any vehicle, whether attended or unattended, upon the paved or main-traveled part of the highway when it is practicable to stop, park or so leave such vehicle off such part of the highway, but in every event an unobstructed width of the highway opposite a standing vehicle shall be left for the free passage of other vehicles and a clear view of such stopped vehicles shall be available from a distance of 200 feet in each direction upon such highway. This section shall not apply to the driver of any vehicle which is disabled while on the paved or main-traveled portion of a highway in such manner and to such extent that it is impossible to avoid stopping and temporarily leaving such disabled vehicle in such position.
Assigned branch(es): In-every-event passage-width and clear-view obligations.
Cell: C135705 (narrow_road, park, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C135705__NRS-484B-440-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
