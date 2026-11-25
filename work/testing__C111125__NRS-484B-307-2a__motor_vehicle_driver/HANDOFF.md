# testing__C111125__NRS-484B-307-2a__motor_vehicle_driver

Status: CPU delivery prepared after production-audit correction. The current proof summary is at the end; Native capture and independent manual source review remain local execution checks.

Exact law: NRS 484B.307(2)(a) — When the signal is circular green alone: Vehicular traffic facing the signal may proceed straight through or turn right or left unless another device at the place prohibits either or both such turns. Such vehicular traffic, including vehicles turning right or left, must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.
Assigned branch(es): Straight movement under circular green alone.
Cell: C111125 (intersection, straight, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Controlled case and Native-source checkpoint, 2026-11-23

The source inventory has zero accepted recordings, so no existing-evidence reuse is claimed. `case-plan.json` now proposes four exact cases: `green_clear`, `green_vehicle_present`, `green_pedestrian_present`, and `green_pedestrian_late`. All use the fixed C111125 straight intersection and sole circular-green signal. Three comparisons vary intersection vehicle presence, adjacent-crosswalk pedestrian presence, and pedestrian region at first green exhibition. The late case preserves the statutory “at the time the signal is exhibited” distinction. No numerical right-of-way threshold or lawful-presence conclusion is invented. Each case has a physical risk assessment. The provided judgment range file has zero entries for this exact law and actor.

`native_scene.py` verifies hashed original map, official signal, straight route, and adjacent-crosswalk sources; checks that the route actually crosses the surveyed intersection; checks real Native map and official signal-head readback; then spawns ego and optional other user through the injected CARLA interface. It destroys spawned actors after a later spawn failure. `measure_attempt` reads hashed original frame events, preserves first green exhibition and each user's original region then, and records later motion separately. It returns no legal verdict. `straight_control.py` supplies conservative approach/hold/proceed engineering control gated by the observed signal and measured user region. `comparison_audit.py` independently rejects wrong exact case pairs, changed fixed-source hashes, missing exhibition data, and missing or incorrect region differences. These modules have not been wired into complete execution bundles or the saved pipeline.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/tests -v`. Six tests pass, including source-hash rejection, actual spawn calls, straight-route geometry, original exhibition timing, controller behavior, and negative comparison audit branches. The result records the hashed log. The exact strict assignment command ran and failed with `Preparation acceptance failed: partial/missing packages remain`, as expected for the truthful partial status. See `cpu-strict-check.log`.

Next CPU work is to connect these case controllers and measurements to each exact construction/config/runner bundle; add a source-hashed diagnostic recipe and selected-requirement finalizer for every case; run each offline and positive/negative compatibility proof; author semantic proposals, execution manifest, saved-only processing tests, and independent delivery audit. A real Native map/head survey and physical replay remain necessary later to prove phase, positions, lawful-presence context and camera visibility. This is not an external blocker for the remaining CPU preparation.

## Saved-only observation checkpoint, 2026-11-24

`saved_attempt.py` now joins a sealed attempt identity to source-hashed site and original frame packets, calls the original-event measurement, and checks all four exact case identities. It requires circular green alone throughout the declared duration, checks the other user's kind and surveyed region at the first exhibition, and verifies later crosswalk entry in `green_pedestrian_late`. The output retains source references, fixed-condition hashes, original frame observations and unresolved lawful-presence/right-of-way fields. It explicitly claims no physical acceptance. The independent `comparison_audit.py` consumes these summaries and checks the three planned fixed-versus-varied pairs.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/tests -v` passed ten tests. New negative tests reject a changed original packet, wrong case identity, wrong exhibition region, missing late entry, short duration and mixed signal aspects. `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2a__motor_vehicle_driver --complete` passed; the exact strict command still rejects the truthful partial status. The test packets are diagnostic and establish no actual Native phase, motion, camera visibility or lawful presence. The declared lawful-presence source in original events still needs a separately sealed reviewed context packet before delivery.

Remaining CPU work: add the exact construction/config/runner bundles and capture/finalizer integration; bind reviewed lawful-presence and other-device context to original sources; write selected-requirement measurement contract, four diagnostic recipes, offline and positive/negative compatibility proofs, canonical stage proposals, execution manifest and independent delivery audit. Then rerun the exact strict gate. Actual map/head survey and physical replay follow CPU preparation.

## Independent saved-media and context audit, 2026-11-24

`delivery_audit.py` takes the sealed four-case packet through `saved_attempt.process_saved`, then verifies a source-hashed camera profile, original frame map and four lossless camera references. It requires each camera frame identity to join the same original event frame, probes 20 Hz/dimensions/full frame count, and full-decodes all camera streams. Production mode requires 900 original frames at the pinned 1080p/720p profile; small CPU fixtures require an explicit diagnostic flag with their injected profile. It source-binds the other-device inventory and participant context matching the original event participant ID and lawful-presence source path. It returns software checks with legal and physical acceptance unresolved. These context files are not a legal determination or evidence of physical visibility.

The focused CPU suite now passes 16 tests, including changed original media, missing camera, lost frames, frame-map mismatch, camera profile drift, changed other-device context, and missing participant context. Command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/tests -v`; see `cpu-delivery-tests.log`. Assignment static check passes; exact scoped strict check still rejects the truthful partial status.

Next CPU work: construct exact runner/config/construction bundles for each case; connect 900-tick Native acquisition and saved finalization; author selected-requirement measurement contracts, source-hashed diagnostic recipes, canonical semantic proposals, execution manifest, offline and positive/negative compatibility proofs, and complete saved-only integration. Actual map/head survey and replay remain for physical review after CPU preparation.

## Original green exhibition acquisition continuation

`native_capture.py` now records 900 consecutive Native ticks at 20 Hz into an original event source for the four exact straight-green cases. It verifies a SHA-bound site packet and all its original map/signal/route/crosswalk references before recording, checks the official head and facing approach on every tick, stores observed lit aspects and ego/other-user positions, and requires a SHA-bound other-user context for occupied cases. It brakes the ego in a guaranteed cleanup path. The original event source is retained if saved validation rejects a later mixed aspect; no receipt is issued for that failure. A tick/snapshot mismatch stops before publication. Successful acquisition feeds `saved_attempt.process_saved` and writes an event/site hash-bound receipt with `camera_capture_complete: false`; four-camera source capture is still CPU work and no physical or legal acceptance is claimed.

`tests/test_native_capture.py` covers a full 900-frame clear case, a source-bound vehicle-present case, tick identity failure and a mixed-aspect failure that retains the original event bytes without a receipt. The full suite passes 19 tests; pinned `runtime.py preflight` and scoped static checks pass. The exact scoped strict command exits 1 on truthful partial status. Four new command logs and SHA-256 hashes are recorded in `result.json`.

Next CPU work: connect actual route control, camera acquisition and world restoration into an exact runner; author four exact constructions, finalizer/measurement contracts, source-hashed diagnostic recipes, canonical semantic proposals and manifest; execute exact offline, positive/negative compatibility and saved-only processing; join their outputs to the independent delivery and comparison audits. Original Native motion, visible phase and lawful-presence conclusions remain unverified. All new scratch ran under `.runtime-work/`; no Git command or frozen/shared file edit was made.

## Original four-camera frame join, 2026-11-24

`native_capture.capture` now optionally consumes a per-snapshot camera callback reader and requires the exact overview, approach, reference-corner and driver-reference views. Every callback must carry the original Native frame ID for that tick. It writes a source-hashed 900-row frame map with the original elapsed time and all four camera IDs, and binds it in the receipt. A missing view, stale callback or mismatched frame fails before original events or receipt publication. This is frame identity acquisition only; the receipt keeps `camera_capture_complete: false` until original media exists and is audited.

Two focused tests cover all 900 frame joins and fail-closed stale or missing camera callbacks. The full assignment suite passes 21 tests (`cpu-camera-join-tests.log`, SHA-256 `a6e53f2b8ce140c31be250a7b13cc78895dedaee8dbc4ff6712fc76f838dffe2`). Pinned preflight passes (`cpu-camera-join-preflight.log`, SHA-256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Scoped static passes (`cpu-camera-join-static.log`, SHA-256 `48e9f59ff0f28d1257ed36d0db584e4dad09e3ef96fbf6b28498472188867f1c`). Exact scoped strict exits 1 because the status remains partial (`cpu-camera-join-strict.log`, SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work is a Native runner that owns four sensor streams, actual route control, world settings and restoration, then creates source-bound media and all four exact construction bundles. Selected-requirement finalization, diagnostics, semantic proposals, manifest, offline and compatibility proofs, and canonical saved processing remain. No legal or physical acceptance is claimed by this frame join.

## Original lossless camera recorder continuation, 2026-11-24

`original_camera_recorder.py` now owns the four original camera listeners for an attempt. It receives callback BGRA images on independent queues, rejects missing/stale frames, wrong source dimensions or malformed buffers before publishing an image, writes ordered lossless PNG scratch, then encodes each view to 20 Hz FFV1 video and returns a sealed attempt-relative source reference. `close` stops listeners, and a failed encode deletes completed partial media. The adapter can be passed as `camera_frame_reader=recorder.read` to existing `native_capture.capture`; the operator-owned runner and final receipt wiring remain CPU work. Its tests use 8×4 fixture images and do not demonstrate real signal or actor visibility.

Twenty-three focused tests including four-view encode/full decode and callback failure cases passed. Pinned preflight and scoped static passed; exact scoped strict exited 1 on truthful `partial`. No exact offline manifest exists yet, so no offline bundle proof can be claimed. Next CPU work: operator-owned runner, integration of sealed media refs with the 900-row Native frame map, exact bundles and offline/compatibility/saved-only proof chain, semantic proposals and independent audits.

SHA-256 source and proof index:

- `original_camera_recorder.py`: `691d3482a74d8301cf79c0aeef2facbef1fe2919a400bfbe148d28c2b62c5a4e`
- `tests/test_original_camera_recorder.py`: `586faffa07f1dc574b99374dce282d619d322ce675941634412c195df572273f`
- `cpu-recorder-tests.log`: `5b5e9ec91c9b65f8ea5b99316902ad3c80c298112bb7601a45434a2e4ee41630`
- `cpu-recorder-preflight.log`: `cac705a2fd913031abca5a004ae61ac7a6cfbe835828722d7c494045ae927b66`
- `cpu-recorder-static.log`: `48e9f59ff0f28d1257ed36d0db584e4dad09e3ef96fbf6b28498472188867f1c`
- `cpu-recorder-strict.log`: `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`

## Original event and four-camera media session join, 2026-11-24

`native_session.py` now wires the 900-tick Native event/frame-map capture to `OriginalCameraRecorder.read`, seals the four FFV1 media refs, joins source-hashed profile and context refs, and calls the independent saved-only `delivery_audit.audit_saved_delivery` full decoder. It publishes `media-capture-receipt.json` with `camera_capture_complete: true` only after the audit succeeds. On audit failure the original capture receipt remains explicitly incomplete. The test joins 900 event/camera frames and proves a failed audit cannot publish a complete receipt; the existing recorder test covers real FFV1 encode/decode with a small diagnostic profile. No real CARLA footage, physical visibility or legal right-of-way is claimed.

Pinned preflight, 26 focused tests and scoped static passed. Exact scoped strict exits 1 on truthful partial. New SHA-bound logs:

- `cpu-session-preflight.log` SHA256 `a3a56efdb818eee16f50801fbdae2f110b6506eff664ff6a67a41191b03e4996` exit 0.
- `cpu-session-tests.log` SHA256 `48ad3f7146069db6fdbb540a1d3d0e253c78ff1319ed5dc0755f5b78c676262c` exit 0.
- `cpu-session-static.log` SHA256 `48e9f59ff0f28d1257ed36d0db584e4dad09e3ef96fbf6b28498472188867f1c` exit 0.
- `cpu-session-strict.log` SHA256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` exit 1.

Remaining CPU work: source-reviewed original site/profile/context, operator world/actor/control ownership, four exact construction and finalizer bundles, canonical semantic proposals/manifest, offline and positive/negative compatibility proofs, saved-only delivery/comparison receipts.

## CPU delivery ready checkpoint, 2026-11-25

Four exact selected cases now have source-gated Native constructions, 900-tick 20 Hz acquisition wiring, four source-surveyed cameras, original signal readback, saved analysis and two tested construction candidates each. The primary and the 0.75 engineering throttle fallback preserve the same law, cell, case, original site and recording contract. Both candidates passed exact offline and positive/negative compatibility checks. The canonical semantic stage chain passed its pinned validator with four selected boundary probes and one explicit incomplete judgment sweep plan; no legal cutoff or verdict is asserted.

Each case passed three measured synthetic physical fixture states (met, not_met, unverified) and an ordered capture/encoder/restoration/Native exit/owner release/saved-processing lifecycle test. Each case also passed saved-only analysis with original input hashes unchanged, an independent positive and missing-camera diagnostic delivery audit, and all three planned comparison pairs passed positive and stale-signal negative audits. The diagnostic fixture outcomes are software proof only. Actual original CARLA motion, official circular-only head, lawful-presence source, visible participants, camera pixels and physical completion must be reviewed during delivery.

The exact scoped command `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2a__motor_vehicle_driver --complete --require-delivery-ready` passed with exit 0 under `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c111125-2a-owner`, `TMPDIR` there, and `PYTHONDONTWRITEBYTECODE=1`. Pinned CPU preflight and the focused test suite also passed. See `result.json`, `cpu-final-strict.log`, `cpu-final-preflight.log`, and `cpu-final-tests.log`.

- Execution manifest SHA-256: `6a1ea71e327310305ff32894d9ddbd0e7bd057a9dc9f7fb3a808c89be5e1fca1`.
- Case plan SHA-256: `820224c17027820f6b76c8db53cd4ac113afd52d4a239e08b83930de495f85df`.
- Semantic index SHA-256: `2a8746d42682ef6c61f52ad89a2328b5c713afc136c56c74edde8665e8fb09cb`.
- Assignment-local queue proposal SHA-256: `e3bf966b01e6d4b7c7fba7583983c19b14bf5ea7608e10d7e456100fea63bae8`. The lead integrates its four exact cases, fallback commands and three comparison audits into the shared queue.
- Scoped strict log SHA-256: `48e9f59ff0f28d1257ed36d0db584e4dad09e3ef96fbf6b28498472188867f1c`.

The first GPU delivery command in `result.json` supplies the exact case and local CARLA variables. The operator must provide `C111125_ORIGINAL_SITE_BUNDLE` after original map/head/route/camera review. The Native runner fails closed when that reviewed bundle or its source hashes are absent or inconsistent; readiness does not claim a physical recording.

## Production source review correction, 2026-11-25

The previous production audit decoded only one RGB frame per camera and accepted saved physical completion without an independent pixel and physical review. That evidence did not support `actual_pixels` or `physical_completion`. The result is reverted to truthful partial and the assignment-local GPU queue proposal is held as a draft.

The Native runner now preserves original camera PNG samples at frames 0, 450 and 899 for every view before sealing. The production audit checks the capture seal source digest, all sealed source bytes, original Native acquisition bindings, encoder closure and world restoration, media receipt, and saved physical source hashes. It compares each preserved PNG RGB buffer with the corresponding lossless decoded video frame and requires a separate manual review bound to the capture seal, saved result, original events and frame map, all camera media, and sampled RGB hashes. The reviewer must record source-frame observations of the circular green, other-user context, ego yield, physical completion and all four views; missing, stale, unverified or nonoriginal-frame review fails closed. It still claims no legal verdict.

The focused test suite includes negative changes to media bytes, restoration, PNG/video pixels, review source hashes, unverified physical completion and frame identity. Actual Native capture and independent source review remain unperformed, so the production audit has not produced an accepted original-source receipt.

Focused suite: 39 tests passed; log SHA-256 `3f66d77c18d206ed25861423b3d32eafdfec5242e704cf642dd87c06bb6f83b8`. The exact scoped strict command was rerun and fails only because `result.json` is deliberately partial; log SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`. Assignment static/complete check passed. No original Native frames or independent review have been claimed.

## CPU proof refresh after production correction

All eight primary/fallback constructions were rehashed and rerun through exact offline and positive/negative compatibility proof after the runner preserved original PNG samples. Four source-preserving saved-only diagnostic runs and four independent positive/missing-camera delivery diagnostics were also refreshed; the production review negatives remain in the 39-test focused suite. The complete scoped static check passed. The production audit intentionally fails closed on a Native attempt until its sealed sources and independent source review exist; CPU delivery preparation is complete without claiming original physical or legal acceptance.

The exact assignment-scoped strict CPU delivery gate passed after refreshing all eight construction offline/compatibility proofs, four physical/lifecycle receipts and saved-only proofs. Strict log SHA-256: `48e9f59ff0f28d1257ed36d0db584e4dad09e3ef96fbf6b28498472188867f1c`. This is CPU delivery readiness only. Original CARLA motion, sampled pixel review, lawful-presence context and independent physical completion review remain local execution requirements before any source acceptance.
