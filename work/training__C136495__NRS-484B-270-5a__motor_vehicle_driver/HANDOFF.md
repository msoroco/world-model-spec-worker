# training__C136495__NRS-484B-270-5a__motor_vehicle_driver

Status: ready (`delivery_prepared`). CPU construction, source-bound compatibility, saved processing, semantic proposals and independent audits are prepared. Physical realization and legal review remain local work.

## 2026-11-23 CPU construction checkpoint

`native/cyclist_response.py` implements two fixed longitudinal response settings for the planned `cyclist_conflict_response` comparison and measures 600 synchronized 20 Hz raw actor samples. It requires rider and bicycle sampled poses/velocities to remain associated, verifies ego/rider/bicycle position changes against the reported velocities at 20 Hz, and returns surface gap, projected time to conflict, ego acceleration and collision-sensor contact count. Its numeric controller settings are engineering choices, not legal thresholds. It cannot infer due care. The implementation requires separate rider and bicycle identifiers and explicit provenance fields, but their contents must be independently verified in a real Native acquisition.

`native/prove_cyclist_response.py` passes a 600-frame, 30-second synthetic fixture and rejects bad mode, missing frame, missing bicycle provenance, broken time join, missing collision sensor source, rider/bicycle pose divergence, rider/bicycle velocity divergence, and a joint pose teleport. The synthetic speeds and identity labels are diagnostic only; no original CARLA velocity or physical bicycle qualification is claimed. The proof log is `native/cyclist-response-proof.log` (SHA-256 `b4acf2bc0251fc9f509b91cdc76c375c99776b23f0fd67981b74c75d4df31ca6`). The controller SHA-256 is `973475b99e67cf433ca269b08becec754e31db4cc43d68f4d91efacd40264fe6` and the proof script SHA-256 is `a9c4bfceafabc0a268bf7a21d545ad67ab7d4a667c7e1c186a3f2f80a8671745`.

This paragraph records the 2026-11-23 checkpoint. The requested CPU artifacts were subsequently prepared as described below. A real Native run, bicycle qualification and physical observation remain unconfirmed.

Exact law: The driver of a motor vehicle shall: Exercise due care to avoid a collision with a person riding a bicycle, an electric bicycle or an electric scooter.

Selected witness scope: Person riding a bicycle. The case plan inventories 3 source topics and drafts one controlled comparison on `cyclist_conflict_response`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining local evidence: actual person riding a qualifying bicycle, motion, camera coverage, physical completion and legal due care require original Native capture and independent review. The selected witness is the bicycle alternative.

Resume: use the first GPU delivery command in `result.json`; perform independent review and acceptance only after original Native capture. There is no accepted original to reuse in this assignment snapshot.

Physical prerequisites: Use an actual bicycle, electric bicycle or scooter rider with approach trajectories, gap, braking and collision evidence.

Legal limit: Due care has no fixed surrogate speed or gap threshold.

## 2026-11-27 delivery preparation

Two exact bicycle-response cases and one risk-based fallback per case are bound in `execution-manifest.json`. The original motor-vehicle driver, rider blueprint, narrow road, 30-second 20 Hz capture, four cameras, measured gap, response command, collision events, original actor poses and media joins are implemented in `native/scene.py`, `native/runner.py` and `finalize.py`. The independent delivery and comparison audit scripts are under `proofs/`; the positive/negative compatibility receipts and physical-completion fixtures are source hashed there. `proposals/semantic-index.json` binds the canonical stage proposals. No fixture establishes a person riding a qualifying bicycle or legal due care; original Native media and classification require independent local review.

Selected cases: `training__C136495__NRS-484B-270-5a__motor_vehicle_driver__selected_a21cf01e__condition_a` and `training__C136495__NRS-484B-270-5a__motor_vehicle_driver__selected_a21cf01e__condition_b`. The comparison `cyclist_conflict_response` varies the requested longitudinal response trigger distance with road, actor, route, camera and duration fixed. This is an engineering contrast, not a statutory cutoff. The law names bicycle, electric bicycle and electric scooter as alternatives; this assigned witness selects a person riding a bicycle. The two cases measure continuous approach and response without inferring a due-care conclusion. No accepted membership or source-backed equivalence reuse exists in the frozen local snapshot.

Saved-only processing was executed for both exact primary cases with `runtime.py process-saved`; logs `proofs/saved-a-positive.log` and `proofs/saved-b-positive.log` report `passed: true`, `recorded_only: true`, original preservation, converter/render/decode and no physical or legal acceptance claim. The commands and log hashes are bound in each manifest `post_capture`. `proofs/unit-tests.log` records 12 passing CPU tests. Resume locally with the first GPU command in `result.json`, then run the independent acceptance and comparison audits against the original Native sources.
