# testing__C158208__NRS-484B-257-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(2) — Except when traffic is being controlled by a police officer or a traffic-control signal: The driver of a vehicle shall stop in obedience to a stop sign or yield in compliance with a yield sign, in compliance with the manner prescribed in subsection 1 [NRS-484B-257-1], prior to entering an intersection if a stop sign or a yield sign is erected at one or more entrances thereto although not a part of a through highway and shall proceed cautiously, yielding to vehicles not so obligated to stop or yield and which are within the intersection or approaching so closely as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Within-intersection instance plus unresolved approaching-hazard sweep..
Cell: C158208 (one_way_to_two_way_intersection, travel, yield_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 12. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 9. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 9 exact law/actor ranges. These are unmeasured construction targets. 6 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## CPU construction checkpoint

Added `nonthrough_yield.py` for four selected-branch probes: an independently occupied intersection, approaching vehicle near/far station requests, and yield-response versus uninterrupted policy. The source-gated lazy constructor requests a non-through intersection with all entrance obligations, a yield-sign approach and another vehicle not obligated to yield, with owned-actor cleanup. Original measurement joins 900 frames, first actual leading-body entry, approach speed, other center/min-vertex stations and across-or-within history. Immediate hazard, cautious proceeding and right-of-way remain unresolved.

Four focused CPU tests pass, including all probes and negative source, obligation, identity, crossing and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because the package remains partial. The 12 frozen accepted recordings have metadata and authored setting descriptions, not original trace/video in this export; the new probes do not claim their physical facts or duplicate their accepted status. Full branch/judgment-range coverage, canonical capture/offline/compatibility, semantic proposals and independent saved delivery/comparison audits remain worker-owned CPU work.

Proof SHA256:

- `nonthrough_yield.py`: `f08a8d23ef30a2f69e417fc5b7b32d68878d6f7f6b114f59a6eade86c1d0f8d6`
- `tests/test_nonthrough_yield.py`: `2202a79f8a4359e1f8504d251554dbfcef7d74c5a38fd410a55ef75ac45bfa79`
- `cpu-tests.log`: `0bf66ed4df0aeb82d4499a3a26b47d99d6b6758734145a93b4ca1649525ca38c`
- `cpu-preflight.log`: `3747878a7d7636776091c2fc5ef7c3a82d38f82fe424ab17c6c0de04b2b1e2ab`
- `cpu-static-check.log`: `2f2b97aa9bfa6487992b94e8adb4cb0fbd4293ea187fd5e1c4698da1bf9062da`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
