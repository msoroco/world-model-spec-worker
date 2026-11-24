# C111125 / NRS 484B.307(8)(d) / cycle or scooter operator

Status: **partial CPU construction, measurement and saved-processing checkpoint**. The fixed assigned witness is a bicycle proceeding straight after failed detection. Zero accepted recordings are listed in the frozen evidence inventory. No physical or legal outcome is claimed.

## Exact cases and comparisons

`case-plan.json` selects five exact cases: `two_cycles_failed_detection` (reference), `one_cycle`, `signal_changes`, `no_prior_stop`, and `fails_to_yield`. The four comparisons isolate observed complete cycle count, failed detection versus a changing signal, antecedent stop, and yielding to a signal-directed participant. Every case retains the C111125 intersection, bicycle, straight maneuver and official traffic light. No numeric legal threshold is invented; the two complete cycles are the statute's count. The packet records all phase transitions because the meaning of the applicable device's cycle boundary still needs original source and legal review.

The statute also names device malfunction, pedestrians and other traffic, three other road-user types, and right/left turns. The assigned witness fixes bicycle, failed detection and straight. The malfunction alternative and separate pedestrian/traffic yield contrasts could be added in this same cell after source review. Right/left turns conflict with this cell's fixed straight maneuver and need lead review of existing compatible cells; this package does not claim those alternatives covered.

## Implemented CPU path

`signal_trial.py` verifies source hashes for map, official device, detector link and bicycle blueprint packet before planning. Its CARLA-lazy `spawn_case` calls the injected Native world blueprint library, reads back the spawned blueprint and actor ID, installs a detector/device policy by injected adapter, and destroys an owned actor on failed setup. `control_step` requests stop, creep or straight travel from current readbacks while preserving each deliberate case contrast. Requested behavior is separate from measured behavior.

`measure_attempt` requires sealed original Native, device, detector and geometry files; the per-frame rows must exactly join those files. It rejects stale hashes, absent channels, discontinuous frames, non-20 Hz timestamps, wrong actor/device/map identity, missing straight entry and nonmonotone route. It measures stationary behavior before the source-bound stop boundary, observed red through entry, sensor-zone occupancy versus output, complete observed green/yellow/red rotations, and directed-participant conflict at entry. The output has no legal verdict or physical acceptance. `comparison_audit.py` independently checks exact pairs, fixed source identities, original bindings, intended measured differences and the reference prerequisites.

`tests/test_signal_trial.py` and `tests/test_comparison_audit.py` cover positive construction, source rejection, all five measurements, actor cleanup and all four comparisons. The fixtures are synthetic CPU packets and do not prove Native execution or video visibility.

`saved_attempt.py` is a CARLA-free saved attempt processor and CLI. It reads an exact `attempt.json` receipt, verifies the packet hash and its four original Native/device/detector/geometry source hashes, checks capture completion, actor readback, detector/device policy authority, frame count and case identity, and then invokes the original measurement path. Its default mode rejects diagnostic fixtures. Diagnostic mode is explicit, retains `diagnostic_fixture: true`, and always returns `physical_acceptance: false` and `legal_verdict: null`. The CLI writes measurement output outside the sealed attempt tree. `tests/test_saved_attempt.py` exercises the CLI plus source tampering, identity, incomplete Native exit, path escape and frame-count rejection. This is a CPU saved-processing component, not the full runtime `process-saved` delivery path.

## Proofs and exact gate

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator/tests -v` passed 13 tests. `cpu-tests.log` SHA256 `31c0e06306808a77360f72834458bda3cd7f831d9a9b243e88efb85e896bf0e6`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete` passed static checks. `assignment-check.log` SHA256 `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete --require-delivery-ready` failed, as expected for truthful partial status, at `Preparation acceptance failed: partial/missing packages remain`. See `strict-gate.log`.

## Exact remaining CPU work

Source a Native C111125 map/device/detector packet and an actor blueprint that substantively represents a bicycle with rider; make the policy adapter observe the detector-to-signal causal link. Bind the capture-time seal and saved processor to the runtime process-saved finalizer. Author full canonical semantic proposals and `semantic-index.json`, exact per-case configurations, source-hashed diagnostics, manifest, offline and positive/negative compatibility receipts, runtime process-saved integration and independent delivery acceptance. Assess whether malfunction and separate participant variants remain within the assigned branch. For the fixed straight cell, refer turns to the lead's branch binding review. Keep status partial until the exact strict gate passes. Then run the prepared GPU queue locally for actual motion, sensor behavior, camera visibility and full video review.

## 2026-11-23 synchronized source-capture checkpoint

`native_capture.py` now accepts post-tick original readbacks through an injected adapter, seals 20 Hz frame identities, writes separate original Native/device/detector/geometry streams, and stores four synchronized PNG camera archives named for the prospective capture profile (`overview`, `approach`, `reference_corner`, `driver_reference`). Each frame records its original camera member and pixel hash. A completed `attempt.json` appears only after all frames and archives have been written and the caller supplies `native_exit_code=0`; a failed exit is rejected before the attempt directory is created. For non-diagnostic capture the writer requires the profile's 1920x1080 overview and three 1280x720 detail images. It does not instantiate a CARLA world or assert physical success.

`saved_media_audit.py` independently reopens the sealed attempt, streams the archive SHA256 checks, verifies contiguous 20 Hz frame identities, joins all four camera members to their per-frame hashes, fully decodes each PNG and checks consistent/profile dimensions. `saved_attempt.py` now requires this audit for non-diagnostic attempts and includes its result in the saved measurement. The diagnostic flag remains explicit and cannot establish delivery evidence by default. The 900-frame CPU fixture decoded all 3,600 synthetic images; negative tests reject a missing camera, a stale archive hash, rehashed changed pixels, wrong profile, and incomplete capture before a receipt can be sealed.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator/tests -v` passed 21 tests, including failed Native completion rejection. `cpu-tests.log` SHA256 `97d5a7ef295d7891d2c4fc6a10c4727bc55b167afacc1f310be92937cbf249ff`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete` passed static checks. `assignment-check.log` SHA256 `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete --require-delivery-ready` remains exit 1 because the package is partial. `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

The capture writer still needs binding to the actual C111125 map/device/detector and bicycle actor, case-specific Native world ownership and device policy adapters, runtime `process-saved`, semantic proposals, per-case offline and compatibility receipts, and canonical delivery/comparison acceptance. No synthetic image or readback is claimed as a physical recording. The source-bound media path is a tested CPU component, not a ready delivery package.

## 2026-11-23 five-case diagnostic bundle checkpoint

`build_offline_draft.py` binds all five exact straight-bicycle red-signal cases to a source-hashed plan, exact case suffix, 20-Hz/900-frame clock and four original camera profile dimensions. The inline constructions embed the source-gated signal/detector planner, synchronized Native capture, saved attempt processor, full PNG media audit and independent comparison audit. The bundled runner checks exact identity and refuses unsourced Native capture. All five pinned `runtime.py offline` checks passed with materializations under `.runtime-work/`; the 22-test focused suite and pinned preflight passed. These are diagnostic drafts, not a canonical delivery manifest or evidence of actual signal cycles.

Proof SHA-256 (logs under this assignment):

- `cpu-tests.log`: `fd8761080e71859f186d4b8bb46be0046784c9bccc0a98aa88b0581ca8e3b9a2` (exit 0)
- `cpu-preflight-bundles.log`: `0ad0074367601c50a2023e0edc39d71ee2548cc363e89fbd10bbd637c54fcdd1` (exit 0)
- `assignment-check.log`: `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035` (exit 0)
- `strict-gate.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-two_cycles_failed_detection.log`: `13b7a98d58bb7302544e11e1fe3a7275e65cd17751c7adad1c9a681748d611a8` (exit 0)
- `cpu-offline-one_cycle.log`: `9e5b0ca5bdd1245c3c962c2a8eae8fedbc180454a1c372339f5477cac3cc0d41` (exit 0)
- `cpu-offline-signal_changes.log`: `2f9652f17395fdf091b852fb4aa47d912a45d374968f176d2ca486355d2ff013` (exit 0)
- `cpu-offline-no_prior_stop.log`: `3f8eb26df53f7a5f9e737092f71137dd5e5122518c2c31e2c04728c9079d7d33` (exit 0)
- `cpu-offline-fails_to_yield.log`: `c3fef82f3e41569807eeced7b3d848263c183b1f0a0dfa0f0723381082959388` (exit 0)

Next CPU work: bind reviewed C111125 original map/device/detector and bicycle-with-rider sources to a production Native owner adapter; author canonical proposals/manifest; run exact source-shaped positive/negative compatibility, pinned process-saved and independent delivery/comparison receipts. Actual two complete cycles, detector-to-signal causality, directed-participant yield, rider visibility and statutory findings remain unverified. Scoped strict fails on truthful `partial` status.
