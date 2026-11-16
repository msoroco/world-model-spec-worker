# training__C146314__NRS-484B-210-2__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.210(2). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

physical clearance sweep for a right-side pass; safety judgment unresolved. Compare only `right_side_pass_lateral_clearance` (m) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## Update 054: source-bound right-pass request construction

`native/build.py` creates a 300 m two-lane one-way OpenDRIVE corridor, 240 synchronized 20 Hz requests for ego and a lead motor vehicle, exact reference/contrast lateral apex requests, and three distinct fallback request policies (reduced paired speeds, elevated overview camera request, later lane-change completion). The requested nominal body gaps are 1.95 m reference and 1.25 m contrast. These are engineering geometry requests, not legal safety thresholds or observed clearance. The two cases remain unselected; no invented Native speed is labeled original.

`.venv-cpu/bin/python work/training__C146314__NRS-484B-210-2__motor_vehicle_driver/native/build.py` exits 0 (`update054-native-build.log`, SHA-256 `3b849777796b1eeb2d41bd199849b839a8bbc6b648511ece809e4f5cb06340f7`). `.venv-cpu/bin/python work/training__C146314__NRS-484B-210-2__motor_vehicle_driver/native/check.py` exits 0 (`update054-native-check.log`, SHA-256 `f1d848508f56c3f8684ac917c6f53547c092e347bcfcc411ae28268ee289e6d1`), validating the authored road lanes, exact current input/plan hashes, eight 240-row trajectories and right-side overtake request. `native/prove_requests.py` passes eight positive candidate checks and rejects a changed lead trajectory and changed lead speed for each of four paired candidates (`update054-request-proof.log`, SHA-256 `6f67694acb5d72bc155dca31179fabfc1c4f629107436cfc3ed8ee16ba406932`). The ordinary scoped checker passes (`update054-scoped-complete.log`, SHA-256 `45942c8d7ae2e75eaeba361f6664b3156570c0e93418e500a12b9777672b012a`).

Next worker-owned CPU actions: implement a lazy CARLA capture runner spawning and controlling both vehicles on the authored road with the pinned four named 20 Hz cameras; retain original actor bodies, velocities, braking and camera-frame joins; derive lateral surface gap, relative motion/time-to-conflict and any hard deceleration from raw sources without fixture-provided channels; author source-hashed synthetic fixtures and positive/negative finalizer tests; select the exact cases, build primary and three fallbacks, run pinned offline, compatibility and actual saved processing; implement independent physical, delivery and comparison audits; bind a canonical manifest and pass scoped strict readiness. Recheck the exact statute and freeze the qualitative safety judgment as unresolved pending physical/legal review. This is unfinished CPU construction, not an external blocker.

The scoped strict readiness command exits 1, as expected for a truthful partial result: `Preparation acceptance failed: partial/missing packages remain` (`update054-scoped-strict.log`, SHA-256 `f105b68de8bd7bbb3e9bdfade14e75a9b56640cac7ca657a4ce02c3efba457fe`). The generated global gate file `runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` still exists (5,687 bytes) under frozen runtime; it was not edited.
