# testing__C157964__NRS-484B-257-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(2) — Except when traffic is being controlled by a police officer or a traffic-control signal: The driver of a vehicle shall stop in obedience to a stop sign or yield in compliance with a yield sign, in compliance with the manner prescribed in subsection 1 [NRS-484B-257-1], prior to entering an intersection if a stop sign or a yield sign is erected at one or more entrances thereto although not a part of a through highway and shall proceed cautiously, yielding to vehicles not so obligated to stop or yield and which are within the intersection or approaching so closely as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Within-intersection instance plus unresolved approaching-hazard sweep..
Cell: C157964 (one_way_to_two_way_intersection, straight, police_officer); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 9. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 9 exact law/actor ranges. These are unmeasured construction targets. 6 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
## November 27 officer-control exception and selected-branch route

The immutable C157964 catalog cell fixes `police_officer` as control. NRS 484B.257(2) begins with an express exception when an officer or signal controls traffic, while the immutable assigned branch requests an occupied-intersection instance and approaching-hazard sweep of the sign-governed duty. The frozen witness names C157964 as a supplemental officer-governance binding from C158208, but the assignment branch text itself still names that sign-governed duty. `officer_exception_binding_audit.py` source-seals both frozen assignments, witness, law text, catalog, batch and current C158208 selected package. Its receipt `officer-exception-binding-audit.json` confirms C158208's seven selected occupied/approaching cases and four controlled comparisons are CPU-ready under `yield_sign`. The receipt does not claim any original physical or legal outcome, nor may it turn C157964 into a yield-sign cell.

`officer_control_measurement.py` is a saved-only source admission and engineering measurement path for a future properly allocated officer exception case. It requires source-hashed sealed original Native result, 900 contiguous 20 Hz frame-map rows, reviewed crossing interval, independent officer-control review and exact video bytes. It separates observed active control, presence without control and unverified control; changed video bytes, rehashed frame gaps and an unseen claimed controlling officer are rejected. Its output has no legal verdict. Five synthetic fixture tests and four allocation audit tests pass (`cpu-officer-all-tests.log`, 9/9). The fixtures do not establish original officer presence or control. Pinned runtime preflight passes (`cpu-officer-binding-preflight.log`) and scoped static check passes (`cpu-officer-static.log`). Exact scoped strict exits 1 (`cpu-officer-strict.log`) because `result.json` remains honestly partial.

The current assignment cannot select its requested sign-governed branch under the frozen officer control. An authorized branch/control reconciliation is needed to use C157964 for an officer exception comparison, while C158208 retains the sign-governed occupied/approaching package. After that allocation, build exact officer Native construction, four-view capture, semantic proposals, manifest, primary/fallback proofs, saved-only and independent delivery/comparison audits, and rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --complete --require-delivery-ready`. No original reviewed officer/video source is present in this export.

| November 27 file | SHA256 |
| --- | --- |
| `officer_exception_binding_audit.py` | `8eb9e611d6dd9f9513a1718819e7e3cf42b4d54fd1809a9c2933e736d42d9bad` |
| `officer-exception-binding-audit.json` | `e0650c3821180cd46375d65562ea4531ba4673ecac923baaa29fd85435ebae89` |
| `officer_control_measurement.py` | `a0a048bd38836e8de769ee257bef06d30c82841da780434492f4b45ce9e2fee2` |
| `tests/test_officer_exception_binding_audit.py` | `400c9e0a2643212e41dc0b81190955a15d2cc93b9a9fd4db27288adb5f8135c2` |
| `tests/test_officer_control_measurement.py` | `18a96e404fb64859bf387cc6f2cc9ba41108383834cec9fff1605aa8153e4c17` |
| `cpu-officer-all-tests.log` | `61c929bc25ddf653d4dd3bba35bbca5a18b341fd147291e711d9e8348ae54ee8` |
| `cpu-officer-binding-preflight.log` | `82752861db5171e56121a6941a2e95ed39837464f80f2b81fb7dd5e62d01be80` |
| `cpu-officer-static.log` | `f32022ac9a5a423291baf7ec7bbecc863c367604b228e46f00fc2c9ce22fefd9` |
| `cpu-officer-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |
