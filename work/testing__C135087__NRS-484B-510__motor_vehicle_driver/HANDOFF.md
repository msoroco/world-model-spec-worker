# testing__C135087__NRS-484B-510__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.510 — A person shall not stop, stand or park a vehicle for any purpose or length of time in any restricted parking zone other than for the purpose to which parking in such zone is restricted, except that a driver of a passenger vehicle may stop temporarily in such zone for the purpose of and while actually engaged in loading or unloading of passengers when such stopping does not interfere with any vehicle which is waiting to enter or about to enter the zone for the purpose of parking in accordance with the purpose to which parking is restricted.
Assigned branch(es): Restricted-purpose entrant during passenger loading.
Cell: C135087 (narrow_road, load_unload, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C135087__NRS-484B-510__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and CPU proof checkpoint

The exact law separates the restricted-zone baseline from the passenger-vehicle loading exception. This assigned narrow-road branch focuses on a restricted-purpose entrant waiting to enter or about to enter during actual passenger exchange. The source text supplies no numeric definitions for “temporarily,” “interfere,” or “about to enter”; `zone_audit.py` retains them as unresolved judgments. The frozen evidence inventory contains zero accepted recordings, so no existing evidence is reused.

`case-plan.json` now names three exact cases: `__clear_before_entry`, `__entrant_during_loading`, and `__entrant_after_exchange`, each prefixed by this assignment ID. Two controlled comparisons vary entrant arrival relative to passenger exchange and subject departure while retaining the zone, restricted purpose, participant roles, parking task, route, camera policy and duration. Each case has a concrete physical-risk assessment. There is no fallback construction yet because the missing site survey prevents a tested failure trigger.

`restricted_zone.py` constructs a zone, subject passenger-vehicle candidate, reserved-purpose entrant and passenger; it assigns the entrant's parking destination and schedules passenger exchange and vehicle motion. Geometry and interval guards reject a subject stop outside the zone, entrant origin/destination mismatches, and departure before exchange ends. The Native adapter remains lazy and requires an independently surveyed map, sign authority, vehicle classification and participant readback. The passenger schedule is an engineering request, not proof of actual exchange.

`zone_audit.py` verifies a sealed 900-frame, 20 Hz original history and source-backed context, including zone boundaries, purpose, effective conditions, vehicle/driver identity, entrant task, exclusion review, passenger boarding-state transition, participant positions/speeds, approach, waiting and access blockage. It returns counts and times without legal verdicts. `compare_cases` rejects absent source references and changed fixed context before reporting physical differences. Six CPU tests cover construction, invalid geometry, original history, source tamper/missing input, incomplete history and comparison mismatch. `cpu-preflight.log` shows pinned CPU tools available; `cpu-tests.log` passes six tests; `static-check.log` passes. The exact strict command in `strict-check.log` exits 1 because status is truthfully partial.

Next CPU work: bind a source-surveyed restricted zone and authority packet to a concrete Native map; implement exact case bundles, per-case original capture and finalizer wiring, semantic proposals, required 4-camera and media audit, candidate-specific offline and positive/negative compatibility receipts, recorded-only processing proof, execution manifest and GPU queue proposal. Keep judgments unresolved and rerun the strict gate after those proofs. Native motion, zone access and camera visibility remain later physical checks.
