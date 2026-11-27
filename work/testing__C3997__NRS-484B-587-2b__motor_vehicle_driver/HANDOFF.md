# testing__C3997__NRS-484B-587-2b__motor_vehicle_driver

Status: partial CPU delivery construction; ten exact cases and nine comparisons are drafted. See current CPU construction below.

Exact law: NRS 484B.587(2)(b); with 484B.587(3), NRS 484B.210(4) — Except if required by an emergency or as otherwise authorized by subsection 3 [(3) appended below], a person shall not drive a vehicle on a controlled-access highway: Across any solid white line that separates an entrance or exit lane from a marked traffic lane. A person driving a vehicle described in paragraphs (a) to (f), inclusive, of subsection 4 of NRS 484B.210 may drive that vehicle on a paved shoulder of a controlled-access highway where lawfully placed signage allows that vehicle to use the shoulder in that manner. The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to: (a) An authorized emergency vehicle described in NRS 484A.480; (b) A vehicle which has been issued a permit to operate as an authorized emergency vehicle pursuant to NRS 484A.490; (c) A traffic incident management vehicle; (d) A tow car; (e) A coroner vehicle; or (f) A public transit motor bus, that is being driven on the paved shoulder of a highway where lawfully placed signage allows that vehicle to use the shoulder in that manner.
Assigned branch(es): Crossing between adjacent traffic and entrance or exit lanes.
Cell: C3997 (adjacent_lanes, change_lane, solid_white_line); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C3997__NRS-484B-587-2b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 current CPU construction

Ten exact cases now cover north/south traffic-lane stay controls, traffic-to-entrance and traffic-to-exit crossings, reverse north crossings, an emergency-necessity contrast, and a separately qualified signed paved shoulder context that does not itself authorize the subsection 2(b) crossing. Nine controlled comparisons are in case-plan.json. outside_lane.py requires a source-hashed finite solid-white marking segment and routes crossing that segment, while lane_native.py records original body vertices and signed/longitudinal relation on every 20 Hz frame. Separate source hashes bind public authority, controlled-access designation, lane functions, marking, qualifying class, paving, lawful sign, emergency record and subsection 3 authorization. analysis.py does not issue a legal verdict.

The 9-test adapted unit suite passes in cpu-tests.log. First current-runtime proof round passed 20/20 primary/fallback offline and positive/negative compatibility checks, then source review tightened finite-segment and qualifying signed shoulder bindings, so those superseded receipts are not readiness evidence. Fresh v6 construction-bound proofs are running under .runtime-work/c3997-owner-nov27/proofs-v6. Final saved-only, physical/lifecycle, independent delivery, final manifest, queue and exact strict gate remain CPU work. Keep status partial until all pass. Original CARLA motion and pixels remain later GPU checks.
