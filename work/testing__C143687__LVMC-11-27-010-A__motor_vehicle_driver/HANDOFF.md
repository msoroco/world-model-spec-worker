# testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.27.010(A); with 11.27.010(B) — Except as otherwise provided in Subsection (B), it is unlawful to operate a motorized vehicle upon or within a right-of-way that: (1) Has been designated on an official trails plan as an equestrian trail, multi-use trail, or other trail not intended for use by motorized vehicles; (2) Has been dedicated to the City for use as such a trail; and (3) Has been posted with appropriate signs to indicate that motorized vehicles are prohibited. The provisions of Subsection (A) do not apply to: (1) An emergency vehicle; (2) Any vehicle that is being used in connection with maintenance of the right-of-way; or (3) Any motorized wheelchair or other device that is designed for and used by a mobility-impaired person.
Assigned branch(es): Conjunctive trail prerequisites, subject to all Subsection (B) exceptions.
Cell: C143687 (nonmotorized_trail, travel, access_restriction_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Construction and source-bound audit checkpoint (2026-11-23)

`case-plan.json` now names six exact cases: all_prerequisites, not_designated, not_dedicated, no_prohibition_sign, emergency_vehicle, and maintenance_vehicle. Five controlled comparisons isolate one official-plan, dedication, sign, emergency-use, or maintenance-use condition against the same baseline. The mobility-device exception remains an explicit compatible-role/cell review, because an ordinary motor-vehicle-driver cell cannot prove qualifying device design and use by relabeling a vehicle.

`trail.py` checks source-backed official plan/dedication assertions, the physical corridor and motor route, sign face and governed access, vehicle/operator records, and separate exception-use status. It installs a sign, spawns a vehicle, applies a route and status, and cleans up owned actors on failure. `saved_audit.py` checks a hash-sealed 900-frame Native history for continuous original frame IDs, stable participants and sources, corridor entry, and sign readback; its comparison audit checks fixed and differing fields. Neither module decides legal compliance or physical video acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver/tests -v` passed 8 tests (see `cpu-tests.log`). `.venv-cpu/bin/python runtime.py preflight` passed (see `preflight.log`). Next: bind source-reviewed administrative and exception records, resolve the mobility-device branch in a compatible allocation, build exact runner/config/measurement contracts and semantic proposals, execute offline and positive/negative compatibility plus saved-only and independent delivery receipts. Actual Native motion, sign visibility and video quality remain later physical checks.

Exact gate checkpoint: `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver --complete` exited 0 (`static-check.log`). The same command with `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain` (`strict-check.log`). This status is truthful: exact delivery artifacts and physical-source bindings remain unfinished.
