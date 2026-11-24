# testing__C150072__LVMC-11-52-136__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.136 — No person shall park a vehicle in an access aisle.
Assigned branch(es): parking in access aisle.
Cell: C150072 (one_way_road, park, access_aisle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150072__LVMC-11-52-136__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `access_aisle.py` with five case probes: full and partial aisle parking, adjacent designated space parking, loading stop, and travel. The source-gated constructor requests an exact one-way approach, vehicle body target and activity, and cleans an owned ego on failure. Original measurement recomputes convex body-footprint overlap on 900 joined frames and checks identity, activity and stop/travel history. It deliberately leaves parking and legal judgment unresolved.

Four focused CPU tests pass, including all five case measurements and negative source/geometry/activity/frame/cleanup probes. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because the result remains partial. The diagnostic site is synthetic fixture geometry; the frozen evidence inventory has no accepted original recording. Canonical capture/offline/compatibility and saved delivery/comparison proofs, physical source-backed site and semantic proposals remain worker-owned CPU tasks.

Proof SHA256:

- `access_aisle.py`: `b1b69357328d9dd7979733b276cd066374b0fb6d5e22830291687d253237f42d`
- `tests/test_access_aisle.py`: `dc1cdd60446f83af122696ed0f15f72694c679f94e712bf640118050f62c2afb`
- `cpu-tests.log`: `202e6eda947743c9202c3c0a01fd100fd8836d0ce314f898ce77bcfa2d043c1e`
- `cpu-preflight.log`: `a9b1dbe3edf5a99dd04530e1ce92a688f44a9f92ec64cc18f6c708cad50b09e3`
- `cpu-static-check.log`: `c3661d5a83e4a4e1201844de28e4e04b7a957103845381da409b761428ffcc27`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
