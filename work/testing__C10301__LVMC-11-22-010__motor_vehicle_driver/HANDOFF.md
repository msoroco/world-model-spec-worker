# testing__C10301__LVMC-11-22-010__motor_vehicle_driver

Status: partial CPU construction. Two exact cases are planned, but neither has a canonical executable bundle or delivery proof.

Exact law: LVMC 11.22.010 — A person shall, when operating a vehicle, give his full time and attention to the operation of the vehicle.
Assigned branch(es): Vehicle operation on an alley route.
Cell: C10301 (alley, travel, access_aisle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## 2026-11-23 construction and proof checkpoint

The exact law has no statutory numeric boundary or explicit exception. The local `judgment_ranges.json` has zero entries for this law and actor; no below/inside/above training probe is available. The law's "full time and attention" phrase remains a judgment about an interior state. Exterior vehicle behavior cannot establish it. `case-plan.json` now lists `__steady_travel` and `__steering_variation` with the same alley route, adjacent striped access aisle, parking space, nominal speed and requested capture channels. `alley_lateral_control_observation` varies the requested lateral profile and requires actual yaw/position measurements; no expected legal label is assigned. The frozen accepted-evidence inventory is empty, so there is no source-backed reuse. The plan records G1/G2 source gaps and the witness's conditional context requirements. Municipal applicability and incorporated-definition scope remain unresolved.

`alley-scene.json` is an engineering geometry candidate. `alley_geometry.py` checks body clearance, access-aisle adjacency to designated parking, and five contrasting stripes. This is an offline geometry check; it does not create Native markings or prove CARLA realization. `attention_measurement.py` reads an exact-case 20 Hz original-shaped operation history, requires stable person/vehicle and frame/time identity and all declared exterior fields, and outputs source-hashed kinematic/device summaries with attention and legal judgment unresolved. It rejects missing sources and invalid identity/time; it is not yet integrated into the runtime finalizer or converter.

CPU proofs: `.venv-cpu/bin/python runtime.py preflight` passed in this turn. `.venv-cpu/bin/python -m unittest discover -s work/testing__C10301__LVMC-11-22-010__motor_vehicle_driver/tests -v` passed eight tests (`cpu-tests.log`, hash in `result.json`). The offline geometry command in `result.json` passed (`cpu-geometry-check.log`). `.venv-cpu/bin/python worker_check.py --assignment testing__C10301__LVMC-11-22-010__motor_vehicle_driver --complete` passed static checks. The exact `--require-delivery-ready` command failed because the result remains partial (`cpu-strict-gate.log`). None of these prove physical attention, camera coverage or canonical acceptance.

## Next CPU actions

1. Realize `alley-scene.json` as a Native alley plus actual contrasting access-aisle marking beside designated parking. Add executable ego route/controller and source-bound original person/vehicle/operation, surface and device capture at 20 Hz. CPU-test fake CARLA calls and both cases without claiming physical success.
2. Build exact case bundles, measurement contracts and canonical semantic proposals. Bind `attention_measurement.py` to actual acquisition and finalization and supply source-hashed diagnostics. Run per-case offline and positive/negative compatibility proofs using the pinned runtime.
3. Bind saved-only processing, independent delivery acceptance and comparison audits with positive/negative CPU fixtures. Assess physical risk for each manifest case; add only a justified fallback with exact proofs.
4. Reread original law and definitions independently, then run the exact strict assignment gate and repair each failing requirement. Keep inputs/runtime/batch frozen.

## Proven checks and dependency boundary

CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
