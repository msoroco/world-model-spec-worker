# testing__C135705__NRS-484B-450-1l__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(l) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: On the highway side of any vehicle stopped or parked at the edge of or curb of a highway.
Assigned branch(es): Highway-side parking on a narrow road..
Cell: C135705 (narrow_road, park, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C135705__NRS-484B-450-1l__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
## 2026-11-23 exact parking construction and measurement checkpoint

The frozen evidence inventory has zero accepted recordings. `case-plan.json` now identifies eight exact cases: highway-side park, behind-vehicle park, highway-side stop and stand, and highway-side stops with separate traffic-conflict necessity, applicable-law, police-direction, and official-device-direction source probes. Seven controlled comparisons hold the narrow-road site, two vehicle bodies, edge vehicle and recording profile fixed while varying the declared endpoint, requested activity or exception context source. No numeric legal cutoff or compliance label is asserted.

`parking.py` validates a source-declared highway, surveyed edge/curb and roadward normal, two distinct target relationships and a sourced approach route; it lazily spawns the edge vehicle and ego, holds the former parked, requests the exact endpoint/activity, and cleans owned actors on failure. `measure_original` checks 900 consecutive original 20 Hz rows, stable actor/source joins, edge-vehicle stationarity, an ego halt and measured terminal lateral/longitudinal relationship. Exception probes require an original context source; whether it supplies a legal exception remains unresolved. CPU fixtures are diagnostic and cannot establish actual edge geometry or legal activity.

`tests/test_parking.py` exercises all eight cases, seven comparison declarations, target geometry, spawn cleanup, original-history measurement and negative source/timing/exception/halt cases. Five focused tests pass. Pinned preflight and scoped static pass; exact scoped strict exits 1 because the package remains partial. No `runtime.py offline` proof exists yet: exact runner/config/manifest bundles still need implementation.

Proof hashes: `cpu-tests.log` `421ff5f1d6a800f3ef17f4eab39b7e2729edd3f3e9e9f0aed0ff227615d1f16b`; `cpu-preflight.log` `584f963d8b7775aab52a1ecd4bb20c8e6ee6178c29f6d91f1b0680a84d4e5633`; `cpu-static-check.log` `eede769f6eeb199083cb78eb3e0c74126d2bdcd95a0b25ef38f44c4418b9c7a2`; `cpu-strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1).

Next CPU work: bind original source bytes and the physical C135705 highway/edge site to a Native adapter and capture; author exact runner/config/manifest bundles and offline, source-shaped positive/negative compatibility; add selected-requirement finalizers, semantic proposals and independent saved delivery/comparison audits. Physical side-by-side placement and original four-camera pixels remain for later Native review.
