# NRS-484B-510 at C135709

Actor: `motor_vehicle_driver`. Frozen cell: `narrow_road` / `park` / `parking_restriction_device`.

Exact statutory source: NRS 484B.510. Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Restricted-zone parking. Planned comparison variable: `restricted_zone_purpose`. Requests: vehicle occupies restricted zone for its posted purpose; vehicle occupies same zone for an unrelated purpose. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the place is a restricted parking zone; the subject stops, stands or parks there for a purpose other than the one the zone is restricted to.

Timing to retain: 'for any purpose or length of time' — no duration makes the wrong use lawful; but the excepted loading stop is 'temporary', so a duration bound for it must be declared; the interference test runs while another vehicle waits.

Exceptions and numeric alternatives planned: a passenger vehicle may stop temporarily while actually engaged in loading or unloading passengers, provided it does not interfere with a vehicle waiting or about to enter the zone for its restricted purpose.

Unresolved judgment or rule composition: the purpose a zone is restricted to is read from its sign; the subject's own purpose is interior state, evidenced only by a passenger exchange. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU saved-measurement construction

Added `native/restricted_zone_measure.py` as a draft saved-source measurement contract for 600 frames at 20 Hz. It consumes `zone.json` and `raw-frames.json` with four named camera identities per frame; it derives in-zone stationary time, passenger activity overlap and waiting/entering vehicle overlap. It records the restricted purpose and subject purpose declaration separately, marks sign authority unverified and returns no legal conclusion. The 0.05 m/s stationary threshold is an engineering diagnostic, never a statutory cutoff. The source observation term mapping is now in `case-plan.json`.

Command: `.venv-cpu/bin/python work/training__C135709__NRS-484B-510__motor_vehicle_driver/native/prove_restricted_zone_measure.py > work/training__C135709__NRS-484B-510__motor_vehicle_driver/native/restricted-zone-proof.json` (exit 0). The proof exercises three 600-frame synthetic positive cases and five negative source failures. Proof SHA-256: `fafbce19f00362ed5294e468ad6ead76a3b284185c74bb44dc6f0b5db6f7b59b`. Measurement script SHA-256: `b572cf365e530539709a81ddfd80df9eb17d01ce9c9664177b137b308401ca4a`. These are diagnostic fixtures; no Native camera video or original source was captured.

Still required: executable narrow-road Native construction and parking controller; sign/zone authority and effective conditions from original evidence; source-bound vehicle/passenger purpose, waiting driver's purpose and all four decoded camera videos; full selected case and exception matrix; exact current-runtime offline, positive/negative compatibility, process-saved, semantic proposals and independent audits. The temporary loading exception must be reviewed on its observed facts without inventing a legal duration threshold. Keep the assignment partial.

## 2026-11-23 CPU parking controller and four-case source proof

Added `native/parking_controller.py` and `native/prove_parking_controller.py`. The controller approaches a 10 m restricted zone, targets a full-footprint in-zone stop, brakes from measured speed, then holds. This is a deterministic motion design for later Native implementation, not a CARLA observation. The proof drives one 600-frame, 20 Hz trajectory through all four exact planned case shapes: restricted-purpose declaration, unrelated-purpose declaration, passenger loading without waiting traffic, and the same loading with contemporaneous waiting traffic. Motion is fixed across the comparisons. The saved-source measurement reports 405 stopped in-zone frames in each shape, 60 passenger-activity frames in both loading shapes, and 100 waiting-vehicle frames only in the interference shape. The purpose variable remains a declaration, sign authority remains unverified, and the proof makes no legal conclusion. Three invalid plans and a nonfinite measured state are rejected. The four camera identity names now follow the pinned capture profile.

Commands (all exit 0, with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` directed under `.runtime-work/`):

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_parking_controller.py > native/parking-controller-proof.json`
- `.venv-cpu/bin/python native/prove_restricted_zone_measure.py > native/restricted-zone-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C135709__NRS-484B-510__motor_vehicle_driver --complete > native/current-static-check.log`

SHA-256: controller `b4d6d1a8f16022d79d32dcb12f8a69a5d5798f139ae3fe9205988d6ca013d321`; controller proof script `4f31cbcda583b09aebd6f8e33036721b4174898b2d0f9673dd1442a16000f494`; four-case proof `dadfd5013b9557b434535df6c4ed69e5eebf5dc119766350450f7c9edb864069`; measurement script `c36a69e51f961841439bfec59f3a1f5954cb2b9448afdb05207164e26987713c`; refreshed measurement proof `42aa8a2bfa9e872b8cf7df6fe815142145395482e091146db918dc4d2a7c9975`; preflight log `04bb3954ebc82b763211f67b530f302b504f1d21412d0c152b6ad2726f969b5b`; scoped checkpoint log `ee4fdb77ff2cc38046458e39da66f028a97dce374ced505020d04b896ccf68f3`.

Next CPU work: implement the exact four-case JSON Native runner, sign and zone construction, participant source acquisition, and four camera streams. Bind each to an execution manifest and run pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. No exact bundle exists yet, so those commands cannot establish a delivery proof. Validate source authority, purpose, temporary passenger exchange and the waiting vehicle's restricted purpose from retained evidence; a self-declared purpose or synthetic door event is not proof. Keep `result.json` partial until those CPU proofs and the scoped strict gate pass.
