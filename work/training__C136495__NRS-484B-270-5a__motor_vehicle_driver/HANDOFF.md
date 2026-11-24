# training__C136495__NRS-484B-270-5a__motor_vehicle_driver

Status: partial. A source-shaped controller and measurement proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/cyclist_response.py` implements two fixed longitudinal response settings for the planned `cyclist_conflict_response` comparison and measures 600 synchronized 20 Hz raw actor samples. It returns surface gap, projected time to conflict, ego acceleration and collision-sensor contact count. Its numeric controller settings are engineering choices, not legal thresholds. It cannot infer due care. The implementation requires separate rider and bicycle identifiers and explicit provenance fields, but their contents must be independently verified in a real Native acquisition.

`native/prove_cyclist_response.py` passes a 600-frame, 30-second synthetic fixture and rejects bad mode, missing frame, missing bicycle provenance, broken time join and missing collision sensor source. The synthetic speeds and identity labels are diagnostic only; no original CARLA velocity or physical bicycle qualification is claimed. The proof log is `native/cyclist-response-proof.log` (SHA-256 `b4acf2bc0251fc9f509b91cdc76c375c99776b23f0fd67981b74c75d4df31ca6`). The controller SHA-256 is `dd69dd9c2398dfaef860cfbc525af2eddeff3552c01a65cc3fe891c838f25d35` and the proof script SHA-256 is `340559f7433a4afaf51e558ea70efa523c1823be5c0c265e59d21bda48068590`.

Next CPU work: identify a real bicycle/rider asset and its wheel, propulsion and moped-exclusion evidence; bind two exact construction bundles and four camera streams to the same narrow-road route; test selected primary and physical-risk fallbacks through offline, compatibility and saved processing; implement semantic proposals and independent delivery/comparison audits. Keep the two cases unselected until these proofs exist. A real Native run and physical observation remain unconfirmed.

Exact law: The driver of a motor vehicle shall: Exercise due care to avoid a collision with a person riding a bicycle, an electric bicycle or an electric scooter.

Selected witness scope: Person riding a bicycle. The case plan inventories 3 source topics and drafts one controlled comparison on `cyclist_conflict_response`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native bicycle physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Use an actual bicycle, electric bicycle or scooter rider with approach trajectories, gap, braking and collision evidence.

Legal limit: Due care has no fixed surrogate speed or gap threshold.
