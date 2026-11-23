# testing__C110969__NRS-484B-450-1c__motor_vehicle_driver

Status: partial CPU observables draft. Nine exact cases and eight controlled comparisons are proposed in `case-plan.json`; none is a realized recording or accepted review result.

Exact law: NRS 484B.450(1)(c) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within an intersection.
Assigned branch(es): Stopping or standing within an intersection.
Cell: C110969 (intersection, stop_stand, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU construction checkpoint

The case IDs are this assignment ID followed by `__outside_reference`, `__inside_stop`, `__inside_stand`, `__inside_park`, `__traffic_conflict`, `__law_direction`, `__officer_direction`, `__device_direction`, and `__through_motion`. The eight comparisons isolate boundary contact, stop versus stand, stop versus park, traffic necessity, law direction, officer direction, official-device direction, and transient motion. The frozen evidence inventory contains no recordings, so each proposed branch retains an original-evidence gap. The exact law supplies no numeric parking duration or legal spatial epsilon; the checker reports original frame observations without issuing a legal conclusion.

`intersection_observables.py` measures original body-footprint contact against a reviewed highway intersection polygon and retains per-frame speed and independent activity/exception context. It requires reviewed highway and joining-roadway basis, matching map IDs, monotonically increasing 20 Hz frames, and all source references. `finalize_observables.py` consumes an exact-case source manifest with SHA256-sealed original boundary, Native trace, and activity packets. It rejects absent or changed packets and attempts to escape the attempt directory. The seven CPU tests exercise contact including edge/crossing overlap, outside control, false/unreviewed joining status, map mismatch, missing activity source, nonmonotonic frames, successful finalization, and tampered trace rejection. The synthetic test geometry demonstrates only software behavior, not actual map geometry, motion or acceptance.

`comparison_audit.py` checks two original measurement records against each comparison's measured fixed-condition and deliberate-difference keys. It rejects missing source seals, absent observations, changed intersection boundaries or fixed conditions, and an unobserved declared difference. It returns no legal judgment. The checker needs actual condition receipts from the runner before canonical comparison delivery; the current test uses synthetic receipts.

`cpu-intersection-tests.log` records eight passing tests. `cpu-static-check.log` records a passing assignment-scoped static check. `cpu-strict-check.log` records the exact strict delivery check failing at the partial-status acceptance line; the substantive delivery artifacts below remain unfinished. `result.json.tests` carries the hashes and exit codes.

## Next CPU actions

1. Integrate an executable CARLA runner/controller for the planned cases. Establish the Native map polygon by reviewed roadway geometry rather than test coordinates, and source actual intentional activity and any claimed exception from original observations. Keep the case and comparison variables fixed.
2. Build the canonical case bundles, measurement contracts, semantic proposals and execution manifest. Bind this finalizer to original capture and saved-only processing, then run each case's exact offline and positive/negative compatibility proofs.
3. Implement and CPU-test independent delivery and comparison audits, including rejection of missing or stale original sources, physical-completion claims without support, and differences in fixed conditions. Assess physical risks per manifest case and add fallback constructions only where justified.
4. Rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C110969__NRS-484B-450-1c__motor_vehicle_driver --complete --require-delivery-ready`. Do not mark ready before it passes.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
