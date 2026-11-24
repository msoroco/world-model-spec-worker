# testing__C147339__NRS-486-341__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 486.341 — Every motorcycle or moped when being driven on the highway is entitled to full use of the traffic lane it is occupying, and a person shall not drive another motor vehicle in a manner which would deprive any such motorcycle or moped of such use.
Assigned branch(es): Protected lane use on a one-way multilane road.
Cell: C147339 (one_way_multilane, travel, motorcycle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147339__NRS-486-341__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
## 2026-11-23 exact protected-lane construction checkpoint

Frozen accepted evidence contains zero recordings. `case-plan.json` now identifies five exact cases: driven motorcycle with ego in adjacent lane, edge intrusion or deeper intrusion; driven moped with edge intrusion; and stationary motorcycle with the same ego edge path. Four controlled comparisons isolate original body intrusion, protected kind and driven status. Full lane use has no invented numeric cutoff; intrusion, spacing and motion are physical context. Motorcycle/moped classification, chapter-specific exclusions and public-highway status require original sources.

`lane_use.py` validates source-declared publicly maintained/accessibly traveled highway status, distinct same-direction lanes, sourced lane and vehicle widths and protected/ego routes with ordered planned body intrusion. Its CARLA-lazy constructor spawns distinct vehicles and requests protected motion plus ego route, with owned cleanup on failure. `measure_original` verifies 900 consecutive 20 Hz original actor rows, stable classifications and sources, protected occupancy and motion, then measures ego body intrusion and center distance. It makes no legal full-use finding. Diagnostic source identifiers in tests are fixtures, not actual highway evidence.

`tests/test_lane_use.py` checks every exact case, ordered adjacent/edge/deep measured intrusion, source and lane isolation, classification, motion, frame/time, absent intrusion and cleanup rejection. Four focused tests pass. Pinned preflight and scoped static pass; exact strict exits 1 with truthful partial. There is no `runtime.py offline` receipt yet because exact runner/config/manifest bundles remain CPU work.

Proof hashes: `cpu-tests.log` `63995df12684c66a855925a351bd6fb1c909e50a8eb8cd5213f7edc952b5cf23`; `cpu-preflight.log` `0526a0fdcc270ba264a823dd2aba036667c73281d4768ea9854323fa79af16e0`; `cpu-static-check.log` `53f08c99fc6b2c3c3693b5cd44b9deb23d14e20ab4b3767827699d2edbc47f32`; `cpu-strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1).

Next CPU work: bind original map/highway/classification bytes and implement a Native two-vehicle/camera adapter, exact runner/config/manifest bundles, offline and source-shaped positive/negative compatibility, semantic proposals, selected-requirement finalizer, saved delivery and independent comparison audits. Physical body overlap/response and original pixels require subsequent Native review.
