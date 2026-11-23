# testing__C150116__NRS-484B-503__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.503 — A person shall not stop, stand or park a vehicle for any purpose or period of time except for the expeditious loading or unloading of passengers in any place marked as a passenger curb loading zone during hours when the regulations applicable to such passenger curb loading zone are effective.
Assigned branch(es): Parking in an effective passenger curb loading zone.
Cell: C150116 (one_way_road, park, loading_zone_marking); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150116__NRS-484B-503__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 worker construction checkpoint

The frozen evidence inventory has zero recordings. `case-plan.json` now specifies seven exact cases: `stop_no_passenger`, `stand_no_passenger`, `park_no_passenger`, `load_prompt`, `unload_prompt`, `load_delayed`, and `park_outside_hours`, each prefixed by the exact assignment ID. Four controlled comparisons cover conduct, passenger activity, release timing and effective hours. The outside-hours case is a condition control, not asserted to satisfy the effective-hours branch. No numeric legal duration cutoff is inferred from the word expeditious.

`passenger_zone.py` validates one-way map readback, source-hashed marked passenger curb polygon and curb adjacency, vehicle/passenger blueprints, applicable regulation, jurisdiction, civil time and timezone before spawning. It commands an ego route and passenger action and cleans up owned actors on failure. `measure_history` requires 900 original contiguous frames and checks actor/source continuity, measured in-zone halt frames and source-backed boarding/alighting events. `saved_audit.py` independently checks the sealed original-history digest, frame join, zone/regulation source and event provenance. `audit_pair` rejects changed fixed sources and missing deliberate differences. These measurements are evidence for later review; they neither decide legal compliance nor prove physical visibility.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150116__NRS-484B-503__motor_vehicle_driver/tests -v` passed 9 tests; log `cpu-tests.log` SHA-256 `a984a9b3ccc0579ced474267af4e24629dab6101d1d83184222168b76bb6b592`. Negative tests reject wrong zone designation, missing boundary source, wrong effective-hours readback, actor changes, missing event source, frame tampering, stale digest and changed comparison site.

Next CPU work: bind an actual source-backed C150116 Native site and applicable civil-time regulation; implement the exact runner, capture/finalizer, semantic proposals and every manifest/candidate and compatibility/post-capture receipt; complete independent four-camera and comparison acceptance audits. Run exact assignment strict gate after those proofs. Actual zone marking, motion and visibility remain later physical checks. Status remains partial.

### Saved-only finalization extension

`finalize_saved.py --history PATH --site PATH --seal PATH --output PATH` now joins a hash-sealed closed original history to a source-hashed site and case ID, invokes the independent history auditor and 900-frame measurement, then writes an atomic JSON measurement. It rejects stale site/history bytes before output. The fixture test exercises the finalizer and both stale-byte negatives; it is not an actual Native capture. The complete focused suite passes 11 tests, retained in `cpu-tests.log` SHA-256 `8b8ebe417b3049463e3e63fe0e8969746c1aada1f67abc92712823e2298aa57c`. The earlier 9-test hash in this report is an intermediate checkpoint; `result.json` names the current suite.
