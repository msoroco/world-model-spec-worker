# testing__C108447__NRS-484B-307-8e__motor_vehicle_driver

Status: partial exact case construction. Six planned case intents and five controlled comparisons; no recording has been accepted.

Exact law: NRS 484B.307(8)(e) — Where the signal is a steady red signal alone: Vehicular traffic facing the signal may not proceed on or through any private or public property to enter the intersecting street where traffic is not facing a red signal to avoid the red signal.
Assigned branch(es): Property bypass at an intersection.
Cell: C108447 (intersection, bypass_signal, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

- `case-plan.json` now covers private and public property bypass, ordinary roadway crossing, non-red approach, red destination, and separately sourced other purpose. Five comparisons reuse the private bypass reference. The frozen accepted evidence inventory has zero recordings; each proposed case maps to that gap.
- `property_route.py` checks original source seals, parcel authority and polygon traversal (including a segment that crosses without an interior sampled point), frame-joined approach and destination signal states, street identity, vehicle class, and purpose as a separate sourced fact. It returns observed predicates and no legal verdict.
- `route_controller.py` validates a source-bound connector in either approach direction and computes bounded low-speed controls. Its CARLA import is lazy. `comparison_audit.py` rejects missing source seals, missing deliberate changes and undeclared fixed-condition changes.
- `.venv-cpu/bin/python runtime.py preflight` passed after the pinned environment update. `.venv-cpu/bin/python -m unittest discover -s work/testing__C108447__NRS-484B-307-8e__motor_vehicle_driver/tests -v` passed 19 CPU tests (`cpu-tests.log`). `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete` passed (`assignment-check.log`).
- Exact strict command: `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete --require-delivery-ready` remains partial (`strict-gate.log`). The general strict exception does not establish completion.
- Continue CPU construction: bind an original Native map/property-authority packet and traversable connector, write the exact runner/config/construction bundles for all six cases and per-case finalizers, semantic proposals, offline and positive/negative compatibility proofs, saved-only and independent delivery proofs, then canonical execution and comparison receipts. Do not infer avoidance purpose from path shape or infer a non-red destination from a green assumption. Actual body route and camera realization are later GPU checks.
