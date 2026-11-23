# C158208 CPU handoff — NRS 484B.257(1)

Status: **partial**. The frozen evidence inventory has zero accepted recordings. The exact branch has a yield sign, no stop line or near crosswalk, and the closest sourced view of approaching through-highway traffic. The case plan retains five selected cases and two controlled comparisons. No Native, physical, legal or canonical acceptance is claimed.

## Current construction and proof

- `native-map-plan/yield-nearest-view.xodr` and `yield_site.py` author and validate a one-way approach to a two-way through highway, a lane-bound yield signal and Native waypoint/sign-trigger readback. The authored map has no stop-line or crosswalk object; actual rendered absence and proper erection remain camera review questions.
- `yield_controller.py`, `yield_construction.py` and `yield_motion.py` stage the five exact case IDs, a through vehicle in each case, slowed/stopped/unchanged ego targets and the already-occupied through-vehicle starting position. Speed targets are engineering choices; observations determine whether the motion occurred.
- `runner.py`, `camera_setup.py`, `camera_encoder.py`, `yield_capture_sources.py`, `yield_control_sources.py` and `yield_interaction_sources.py` implement synchronized overview, approach, reference-corner and driver-reference source capture, original frame and sight rays, Native control inventory, actor bodies and cleanup. The saved path uses `yield_context.py`, `yield_measurements.py`, `prepare_review.py` and `finalizer.py`. Camera review remains unset until real source frames exist.
- `build_construction.py` binds 19 current source files into `construction.json`. `execution-manifest.json` is a **draft** with the first selected case only. The first exact case `yield_nearest_slowed` passed `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__yield_nearest_slowed --output .runtime-work/c158208-first-offline-20261122-b --python "$PWD/.venv-cpu/bin/python"`; the returned hash-bound log is `primary-offline.log`. Eight source and staging tests pass in `cpu-tests.log`. The partial scoped worker check passes.

## Next CPU work

Build a C158208 diagnostic source recipe, then run first-case positive and missing-source negative compatibility and recorded-only saved processing against the materialized first construction. Review its derived channels and finalizer output. Expand three measurable-risk fallback constructions for each of the five exact cases and prove offline, compatibility and saved processing for each. Add the remaining four primaries, semantic stages, independent delivery/comparison audits, and a complete execution manifest. Run the scoped strict gate before changing status to ready.

The physical operator must later verify the Native sign face/governance, absence of stop line and near crosswalk, nearest-view sight, actual vehicle motion, continuous crossing interaction and all four original camera views. The plan's first GPU command is prospective and its manifest will need the complete CPU proofs first.

Generated assets are under `.runtime-work/`. No frozen input, runtime or batch file was edited and no Git command was run. A reversible archive of historical C158190 logs is in `work/_shared/archived-c158190-unbound-audit-logs-20261122.json`; its ready status is independently rechecked after each archive change.
