# C422976 LVMC 11.46.030 school pedestrian lane

Status: partial CPU construction checkpoint, 2026-11-26. Original physical recording, legal classification, and delivery readiness remain unclaimed.

The frozen assignment has no accepted exact recording and no matching judgment range. The legal witness concerns the nearest side of a school pedestrian lane, a stationed child-crossing warning, a complete vehicle stop at least fifty feet away, and a release condition before proceeding. The engineering targets do not establish a legal measurement convention or verdict.

## Current construction

`case-plan.json` and `proposals/cases.json` now select 15 exact cases and 12 comparisons. Nine variants isolate 49, 50, and 51-foot stop requests, human and device warning, a human go signal, departure, continued warning, premature proceed, no warning, and presence without child warning. Six finite judgment sweep cases vary authored warning or departure onset time across three stations each, while original timing is measured separately. Both legal judgments stay unresolved. The pinned semantic stage validator passes.

`reviewed_site.py` rejects missing, changed, or escaping site/map/geometry/actor source packets. `school_lane_controls.py` maps every selected variant and sweep point to a distinct 900-frame, 20 Hz control request after source validation. `school_lane_observations.py` rejects stale or synthetic original receipts and measures source-bound 20 Hz vehicle reference distance and cessation without a legal conclusion. `runner.py` validates exact selection and capture configuration. `native_adapter.py` now acquires the reviewed map, actors and four cameras and records raw original frames and motion, but human/device warning and release actuation and readback still require a reviewed original source mechanism; the Native path has not been physically run.

`build_constructions.py` built 15 distinct inline constructions and a diagnostic execution manifest. Pinned `runtime.py offline` passed on every selected case; per-case logs and hashes are listed in `offline-proof-summary.json`. Offline success proves materialization, entrypoint checks, and bundled CPU tests only.

## Current CPU receipts

- Runtime CPU preflight: exit 0, `cpu-preflight.log`.
- Unit suite: 17 tests passed, `cpu-school-tests.log`.
- Offline construction proof: all 15 selected cases exit 0, `offline-proof-summary.json` and per-case `offline.log` files.
- Pinned semantic stage contracts: exit 0, 15 selected cases and 12 comparisons, `cpu-semantic.log`.
- Assignment partial check: exit 0, `assignment-check.log`.
- Exact strict check: exit 1 on truthful partial result, `strict-gate.log`.

## Next worker-owned work

Complete reviewed human/device warning and release actuation/readback in the Native adapter and verify original four-camera capture. Complete exact per-case constructions, diagnostic recipes, measurement finalizer, offline and compatibility proofs, and independent saved, physical, lifecycle, delivery, and comparison audits. Then bind current hashes in the execution manifest and canonical queue proposal, re-run all CPU proofs, and run the exact scoped strict gate. Actual CARLA realization and independent source review remain later physical checks.
