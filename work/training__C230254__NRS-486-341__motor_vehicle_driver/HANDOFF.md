# training__C230254__NRS-486-341__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 486.341: Every motorcycle or moped when being driven on the highway is entitled to full use of the traffic lane it is occupying, and a person shall not drive another motor vehicle in a manner which would deprive any such motorcycle or moped of such use.

Cell: road / travel / motorcycle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

motorcycle traveling in occupied lane; other motor vehicle ego alongside Vary only `motorcycle_lane_use_deprivation` (category) across ['full_lane_available', 'blocked_by_ego']. Measure lane polygon, both full footprints, lateral clearance and motorcycle control response. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Deprive of full use is qualitative and remains legally unresolved. Resolve exact statutory branches from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## 2026-11-23 CPU measurement construction

`native/lane_use.py` now computes protected-vehicle and ego footprint area, fractional occupancy of the same mapped lane, inter-vehicle surface gap, and overlap area from synchronized convex polygons. Its joined-frame path rejects missing frame numbers, nonincreasing timestamps and absent Native source references. `native/test_lane_use.py` proves disjoint adjacent, partial lane entry, footprint overlap, winding independence and invalid geometry rejection. The command `PYTHONPATH=work/training__C230254__NRS-486-341__motor_vehicle_driver/native .venv-cpu/bin/python -m unittest -v test_lane_use` passed (7 tests); output is `native/lane-use-unit-proof.log`, bound by SHA-256 in `case-plan.json` and `result.json`. The assignment-scoped `worker_check.py --assignment training__C230254__NRS-486-341__motor_vehicle_driver --complete` passed static validation.

The exact law protects both motorcycles and mopeds. The C230254 catalog control identifies a motorcycle, but classification must be established from chapter-specific source facts. The frozen witness also asks for public-maintenance and vehicular-access evidence for the chapter 486 highway. No statute-provided clearance cutoff is available. Collision, longitudinal overlap, ego lane change and motorcycle deviation are potential evidence, not mandatory elements. `case-plan.json.source_review_20261123` records these distinctions. The geometry module makes no legal classification and still needs retained Native pose, bounding-box, lane-map and vehicle/highway context sources. No CARLA or saved-processing proof has been claimed.

`native/finalize_lane_use.py` consumes saved source-shaped JSONL and writes one measured JSONL row per contiguous source frame. The seventh CPU test executes that path, checks preserved source references and the measured gap, and rejects a missing source. This is a module-level saved-only proof, not the runtime `process-saved` pipeline or Native acquisition proof.

## 2026-11-27 original source sampler checkpoint

`native/acquire_lane_use.py` samples actual CARLA actor bounding boxes and the protected actor's mapped traffic-lane waypoint after synchronous ticks. It retains actor identities, projected full footprints, the local mapped lane strip, lane width and source references for the saved finalizer. The strip is a documented finite measurement window and no legal lane-use or clearance threshold. The sampler still needs invocation by an exact Native runner and a preserved chapter 486 highway/classification context source; the control label alone cannot prove classification. The moped alternative remains outside the current motorcycle cell construction and needs a compatible scene binding.

`PYTHONPATH=work/training__C230254__NRS-486-341__motor_vehicle_driver/native .venv-cpu/bin/python -m unittest -v test_lane_use test_acquire_lane_use` passed 11 tests. Its log is `native/lane-use-unit-proof.log` (SHA-256 `9ebb9481cbf08d4da4b4c6e6c3081ea92f90df305f4ab2416382e180c25bef8a`). These tests exercise yaw projection, map lane geometry, acquisition-to-finalization, four-camera frame joins, hashed chapter 486 context citations, missing source rejection and distinct actor identity. They are CPU fakes, not physical realization. The new `finalize_bound` path requires the saved map, acquired geometry and cited chapter 486 context; it has not been wired into `runtime.py process-saved`.

The exact scoped `worker_check.py --assignment training__C230254__NRS-486-341__motor_vehicle_driver --complete` passed static checks. The strict `--require-delivery-ready` command fails because `result.json` remains partial. Next: implement exact runner and classification/highway source survey, bind its acquired files into runtime-compatible saved finalizer, build two selected exact constructions with source-bound positive and missing-source negative receipts, then semantic proposals, physical checks, independent delivery/comparison audits and the strict gate. Preserve partial status until those proofs pass.
