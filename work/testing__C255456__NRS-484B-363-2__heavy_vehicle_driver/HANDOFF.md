# testing__C255456__NRS-484B-363-2__heavy_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.363(2); with 484B.363(9) — A person shall not drive a motor vehicle at a speed in excess of 25 miles per hour in an area designated as a school crossing zone except: (a) On a day on which school is not in session; (b) During the period from a half hour after school is no longer in operation to a half hour before school is next in operation; (c) If the zone is designated by an operational speed limit beacon, during the hours when the pupils of the school are in class and the yellow lights of the speed limit beacon are not flashing in the manner which indicates that the speed limit is in effect; or (d) If the zone is not designated by an operational speed limit beacon, during the times when the sign designating the school zone indicates that the speed limit is not in effect. As used in this section, “speed limit beacon” means a device which is used in conjunction with a sign and equipped with two or more yellow lights that flash alternately to indicate when the speed limit in a school zone or school crossing zone is in effect.
Assigned branch(es): Heavy motor vehicle at a school-crossing-zone crosswalk.
Cell: C255456 (school_crossing_zone, travel, crosswalk); actor: heavy_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C255456__NRS-484B-363-2__heavy_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
