# testing__C111304__NRS-484B-653-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.653(1)(a) — It is unlawful for a person to: Drive a vehicle in willful or wanton disregard of the safety of persons or property on a highway or premises to which the public has access.
Assigned branch(es): Intersection travel with person and property context.
Cell: C111304 (intersection, travel, person); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and source-audit checkpoint

Status remains partial. The frozen evidence inventory has zero accepted recordings. `case-plan.json` now names eight exact proposed cases across highway person encounter (northbound and southbound), property proximity, and public-access-premises person encounter, with five controlled comparisons. They are planned captures, not accepted evidence or Native executions. Public-access premises must have a source-hashed site; C111304 catalog metadata alone does not establish one. The willful/wanton term has no numeric worker cutoff or automatic legal label.

`encounter.py` implements source-gated map-lane and public-access checks, separate ego and crossing vehicle spawns, fixed occupant registration, property placement, route commands, failure cleanup, and original synchronized distance/speed measurement. `saved_audit.py` independently requires a hash-matched 900-frame original history, stable identities/map/site/camera context, occupancy join, and source-bound controls; it also rejects missing comparison differences and changed fixed conditions. Nine CPU tests pass, including negative branches, in `cpu-tests.log` (SHA256 `e1723f501ded87c3b9334363c16a229e0c3d5312266e62c3004f459529294b1f`).

The exact command `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` still fails with partial/missing packages; see `strict-check.log`. Next CPU work: bind a concrete source-hashed Native site and adapter; author the exact runner/manifest and selected requirement finalizer for each case; run offline and positive/negative compatibility receipts, semantic proposals, full delivery and video audit, and source-bound comparison proofs. Physical motion and four-camera pixel visibility then require local Native execution.

## 2026-11-24 original Native acquisition and saved-source checkpoint

`native_acquisition.py` now provides a lazy adapter-driven 900-frame, 20 Hz acquisition for all eight planned exact cases. It requires an original sourced site/map/camera plan and matching public-access basis, records ego/crossing/occupant/property original actor and control packets, checks occupancy and stable identities, and records four original camera readback hashes for every frame. It rejects missing frames, cadence gaps, a missing camera, unchanged actor identities, and absent actor movement. On success it writes sealed `original-history.jsonl`, `original-packets.jsonl`, `original-cameras.jsonl`, and `native-receipt.json` into the operator-supplied attempt directory. It brakes ego and destroys constructed actors on both success and failure. The adapter must bind its operations to the original CARLA world; the fixture tests only verify the software contract.

`saved_audit.py audit_native_acquisition` independently reopens the three sealed files and rejoins every actor/control packet, frame, 20 Hz elapsed time, site/map/camera plan, occupancy, and four camera readback hashes. It explicitly leaves full-video decode, actual pixels, physical completion, and legal judgment unresolved. `tests/test_native_acquisition.py` exercises complete 900-frame acquisition, saved rejoin, tampering, missing camera, actor frame mismatch, occupancy mismatch, source basis mismatch, cleanup, and attempt overwrite rejection. The full assignment suite has 13 passing CPU tests in `cpu-tests.log`. The scoped static command `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete` exits 0 in `cpu-static-check.log`; the exact strict command with `--require-delivery-ready` exits 1 in `strict-check.log` because the package remains partial.

Next CPU work: bind the adapter to a reviewed source-hashed C111304 highway/public-access-premises site and actual four-camera sensor bytes; author exact per-case runner, manifest, finalizer/converter and semantic proposals; run per-case offline and positive/negative compatibility; add source-bound full-video delivery and fixed-condition comparison audits. No actual Native run or pixels were claimed by this checkpoint.

## 2026-11-24 saved-media and measurement checkpoint

`media_audit.py` now independently verifies a four-camera saved-media inventory against the sealed Native receipt and a source-hashed camera plan. It rejects missing, reused, redirected or hash-changed encoded files; checks exact 900-frame, 20 Hz metadata and configured dimensions with ffprobe; and fully decodes each file with ffmpeg. The synthetic fixture creates four small 900-frame videos only in a temporary test directory. It proves the CPU decoder path, not actual body visibility or correspondence between compressed pixels and original sensor packet hashes. `saved_audit.finalize_saved_measurements` independently rejoins all sealed acquisition sources before applying the original actor-history measurement, and refuses a foreign exact case or a modified history.

The 17 focused assignment tests pass in `cpu-tests.log`. Scoped static check exits 0 in `cpu-static-check.log`. Scoped strict delivery check exits 1 in `strict-check.log` because status remains partial. Outstanding CPU work: source-reviewed actual highway and public-access-premises map packets, CARLA world/camera adapter binding, eight exact runners and manifests, semantic proposals, per-case offline and positive/negative compatibility, saved processing and source-bound comparison proofs. Actual Native execution and visibility checks follow the CPU package. No numeric definition of willful or wanton conduct is asserted.

The acquisition and independent saved audit now additionally bind each original control packet to the exact case's ego target speed, crossing target speed and crossing release time. This closes the earlier risk that a timing comparison could rely only on planned values. The late-case positive and wrong-release negative tests pass. The media audit defaults to rejecting diagnostic footage; the synthetic fixture is admitted only by an explicit test option. Current focused suite: 18 passing tests. `result.json` contains hashes for the current passing test and scoped static logs.

## 2026-11-24 loaded-site source binding

`site_binding.py` now binds a case's actual loaded OpenDRIVE bytes and map name to the site packet, joins a separately sourced public-access review and source document, verifies the camera-plan hash, and then applies encounter site validation. Highway and premises variants both pass diagnostic fixture tests; map, access-source, and camera-plan drift are rejected. Diagnostic review is accepted only with the explicit `allow_diagnostic=True` test option. No original C111304 site packet or public-access review has been supplied or claimed. Lane waypoint geometry and real access status still need review against original sources. Current focused suite: 20 passing tests; scoped static exit 0 and strict exit 1 with truthful partial status.

## 2026-11-24 source-bound timing comparison checkpoint

`saved_audit.audit_saved_timing_pair` now reopens and independently rejoins both 900-frame sealed Native attempts for each declared northbound, southbound, or premises early/late timing pair. It checks exact case order, original actor/control/camera packet hashes, common site/map/camera/public-access and speed/fps/duration sources, unchanged actor blueprints, ordered release commands, and a real difference in measured ego-to-occupant center distance. It retains source and receipt hashes and makes no pixel, physical-completion, or legal finding. Positive and negative CPU tests reject reversed cases, modified packets, changed fixed map, identical measured encounter, and unsupported pair IDs. This is a proof of the comparison-audit code using diagnostic fixtures, not original C111304 evidence.

The focused suite passes 23 tests (`cpu-tests.log`); scoped static check exits 0 (`cpu-static-check.log`). The exact scoped strict command exits 1 (`strict-check.log`) because this assignment is still partial. Remaining CPU work includes source-reviewed highway and public-access-premises map packets, CARLA world/camera adapter binding, eight exact runner and manifest bundles, semantic proposals, per-case offline and positive/negative compatibility, full saved delivery, and source-bound property-position and approach-direction comparison audits. Physical motion and camera visibility still require Native execution.
## 2026-11-23 exact offline diagnostic bundle checkpoint

`build_offline_draft.py` packages each of the eight exact C111304 cases with unchanged encounter, Native acquisition, site binding, saved, and media audit source; its inline `config.json` binds the selected case spec, the plan SHA256, 900 original frames at 20 Hz, four cameras, and required original sources. The runner validates these bindings and refuses unsourced Native capture. `execution-manifest.draft.json` is diagnostic only; it is not a canonical delivery manifest. No physical or legal outcome is inferred.

`tests/test_offline_bundle.py` verifies each construction SHA and source copy, complete exact-case coverage, and the five controlled configuration variations. The focused suite passes 25 tests; pinned runtime preflight and scoped static checks pass. Each exact `runtime.py offline` command exits 0 and reports `simulation_started: false`:

- `cpu-offline-person_north_early.log` SHA256 `904e89f1d03f04432328f39502d404c24b8cdb665f535daba53c970c2e5992e0`.
- `cpu-offline-person_north_late.log` SHA256 `ba7f5bfcec0874595673340af5c05435a42b08ce78084c6ff0c8982cd0567957`.
- `cpu-offline-person_south_early.log` SHA256 `be72e0350a7a447d518e68b4cd369933679bdf2173c827c3e3a275fd5039c104`.
- `cpu-offline-person_south_late.log` SHA256 `c5e678dae3ff5c545090a532432e3b8c5d67957f435d358515a3cec3ed2eeb62`.
- `cpu-offline-property_near.log` SHA256 `c547691219d759f7649a2876e96c79b2eab54f8391c08a6c3b038218bbbdf6d6`.
- `cpu-offline-property_far.log` SHA256 `c7c71fce81c1dc54c4698a1373549b7b13bd8121023023caa438cede4b94eaa4`.
- `cpu-offline-premises_person_early.log` SHA256 `0eba9cedf9ec40a20f379822d0fe5817748b859bc2c56c9897a2bc6ae2ed0833`.
- `cpu-offline-premises_person_late.log` SHA256 `a18e95b9f9fcac971acf679f929471904321786da87ad73f460f8877c8d010c8`.

Other proof hashes: `cpu-tests.log` `1d41e224a81184e42ea560aada7643f636681f7ab9dec732545864fb6bac0a86`; `cpu-preflight-bundles.log` `8ed8e83e191ef2ee6576c16ff729ef759a58f355a687575729e012a9369c72d4`; `cpu-static-check.log` `474d50a70a3c70eb63d92525483a56f036392efa4cd4bd434fe9f4b3e25ab296`; `strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1, truthful partial).

Next CPU work: bind reviewed original C111304 highway and public-access-premises site packets and a CARLA world/camera adapter; promote all eight bundles to executable Native delivery runners and canonical manifest; supply exact semantic proposals, selected-requirement finalizers, positive/negative compatibility, saved processing and independent delivery/comparison receipts. Physical motion, original pixels, capture quality, and willful/wanton legal judgment require subsequent original review.

## 2026-11-23 saved property-position comparison checkpoint

Added `saved_audit.audit_saved_property_pair` for the exact `property_near` and `property_far` comparison. It independently reopens both sealed 900-frame Native captures, verifies exact case identities and fixed site, map, public-access, camera, speed, release, frame rate, blueprint and actor conditions, then requires distinct original property positions and measured near/far ego-to-property distance order. Distances remain engineering observations only; no damage, visibility, physical completion, or willful/wanton legal conclusion is inferred. Negative tests reject swapped cases, a tampered source packet, unchanged property position, and changed map source. The focused suite passes 27 tests. All eight diagnostic constructions were regenerated to copy revised audit source, and all eight offline checks pass without starting simulation. Pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial status. Reviewed original site/actor/camera capture, canonical delivery, compatibility and approach-direction saved comparison remain CPU work.

- `cpu-offline-person_north_early-property-pair.log` SHA256 `37796eda848167c5bdf0407e88229d2eaece27ab38b80ff112ba89d0cb81a8ce`.
- `cpu-offline-person_north_late-property-pair.log` SHA256 `c35928b8d7952d8bf47e2c534d96f839cc3f0b98d9de0532cdc5f61505295f2e`.
- `cpu-offline-person_south_early-property-pair.log` SHA256 `0f96e746c3b65fca1fa0b311bbdffe9ca6acb1975b4243dccad00c9d6018c77c`.
- `cpu-offline-person_south_late-property-pair.log` SHA256 `69c3a0cda0dccb8ada44e5ad44c6bdb1ce39f95a532f074fbadec52888d99988`.
- `cpu-offline-property_near-property-pair.log` SHA256 `05655dc31afab8a30483ff5fbf9592f4cf11105176d1185d51fa10b9af8c7591`.
- `cpu-offline-property_far-property-pair.log` SHA256 `11635cc07564f6429365d4881ec03f010747919a0796a1ee3a3e3cd08939e209`.
- `cpu-offline-premises_person_early-property-pair.log` SHA256 `43997fdc1ef6f4c78429d9bc7abe25efce168cfbb6002074080cb0c7485914fe`.
- `cpu-offline-premises_person_late-property-pair.log` SHA256 `6bdb03495c66100cffaa20ca46133bedf4eff90f6997e37cf3335db94515efbd`.
- `cpu-tests-property-pair.log` SHA256 `e6609fce2254f49b6cb355b0b8bd8d2979232bdbcdc1e5ded8f6d2131363d0e0`.
- `cpu-preflight-property-pair.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `cpu-static-property-pair.log` SHA256 `474d50a70a3c70eb63d92525483a56f036392efa4cd4bd434fe9f4b3e25ab296`.
- `strict-property-pair.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

## 2026-11-24 saved approach-direction comparison checkpoint

`saved_audit.audit_saved_approach_pair` now independently reopens the exact highway `person_north_early` and `person_south_early` sealed Native attempts. It rejoins original actor/control/camera packets through the existing saved finalizer, requires identical site, map, camera, public-access, speed, release, frame-rate and actor context, and computes original ego start-to-end displacement from the 900-frame histories. It rejects negligible motion and requires the measured vectors to oppose each other. The returned cosine and displacements are engineering observations, not a physical safety or willful/wanton legal finding.

Two new tests prove the positive diagnostic comparison and reject reversed case identity, modified original packets, same-direction motion and changed map. The full 29-test suite passed. All eight exact diagnostic constructions were regenerated to carry the updated audit and passed pinned offline; pinned preflight and scoped static passed. Exact scoped strict exited 1 on truthful partial status. The thirteen current command/log SHA-256 receipts are in `result.json`.

Next CPU work: source-reviewed original highway and public-access premises site packets, concrete CARLA actor/sensor/controller binding, canonical semantic proposals and execution manifest, exact positive/negative compatibility, saved processing and complete delivery/video comparison receipts. Actual Native motion, camera visibility and legal state of mind remain unverified.

## 2026-11-24 source-gated CARLA and saved-camera processing checkpoint

`carla_adapter.py` now binds reviewed numeric northbound, southbound and crossing route waypoints, vehicle and visible occupant/property blueprints, a source-defined property offset axis, 20 Hz synchronous world readback, control commands, four RGB camera transforms and callback dimensions. `native_runner.py` accepts one of the eight exact case suffixes, passes the site through `site_binding.bind_world_site` before world mutation, and restores the world and owned actors after success or failure. No original C111304 site, public-access review or camera packet has been supplied; the runner requires those external source files at local execution and makes no claim that the diagnostic site is real.

The adapter saves the exact PNG bytes handed to `native_acquisition.capture` under the local attempt directory; the sealed camera trace hashes the same bytes. `saved_media.py` reopens all 900 original PNGs per camera, compares each with the sealed original-camera frame hashes, creates four 20 Hz FFV1 streams, then calls the independent full-stream `media_audit.audit_media`. It rejects missing or changed PNGs before conversion. This is a CPU-tested saved-processing path, not original captured footage or a finding of pixel visibility, physical completion, or willful/wanton disregard.

`tests/test_carla_adapter.py`, `tests/test_native_runner.py`, and `tests/test_saved_media.py` exercise both approach lanes, property offset, attached occupant, four camera callback sources, source rejection before world mutation, cleanup after capture failure, a complete 900-frame synthetic source-to-FFV1 audit, and changed-PNG rejection. The complete assignment suite passed 36 tests in `cpu-carla-binding-tests.log`. All eight exact diagnostic constructions were regenerated with the new source files and all eight `cpu-carla-offline-*.log` offline checks passed without simulation. Scoped static check passed in `cpu-carla-static.log`; exact scoped strict check exited 1 in `cpu-carla-strict.log` because result status remains partial. Current passing receipt hashes and commands are in `result.json`.

Remaining CPU work: obtain and review original highway and public-access-premises site/access documents and numeric map/actor/camera packets; replace diagnostic-only bundles with a selected delivery manifest and exact finalizer; author canonical semantic proposals, source-shaped positive and missing-source compatibility, and source-bound delivery/comparison receipts. The adapter's attached visible occupant must be verified against the original local CARLA asset and camera pixels before any physical acceptance. Actual Native execution, motion and image quality remain later local checks.

## 2026-11-24 canonical semantic and selected-manifest checkpoint

`build_semantic_draft.py` now authors source-hashed relevance, template, value-free judgment-observable requirements, bindings and exact case proposals. The proposal preserves the willful/wanton phrase without assigning a numerical cutoff or legal outcome. One physical sweep remains explicitly incomplete until an original reviewed site and feasible controller range can be bound. Direct `semantic_delivery.validate` on the selected manifest passed six stages and all eight selected cases (`cpu-semantic-validation.log`). The canonical recording description matches every regenerated construction.

`build_selected_manifest.py` pins all eight exact constructions to their latest passing offline receipts and the runtime source manifest. It explicitly records partial preparation and pending compatibility/delivery receipts. The materialized `runner.py` now forwards the reviewed site, public-access source/review, camera plan, host, port and output directory to `native_runner.run`; the runner accepts package files already materialized in the attempt directory and refuses prior source/acquisition files. A focused test covers this dispatch path. The assignment suite passed 38 tests in `cpu-semantic-tests.log` after the final runner change, and eight `cpu-semantic-offline-*.log` checks passed without simulation. Scoped static passed; scoped strict still exits 1 because `result.json` truthfully remains partial.

Next CPU construction is the canonical Native `capture/` evidence projection, source-derived trace/frame-map/recording streams and result finalizer, followed by source-shaped positive/missing-source package compatibility and independent saved delivery/comparison receipts. The diagnostic FFV1 tests establish the saved processing code path only. No original C111304 driving or camera visibility has been accepted.

## 2026-11-24 sealed Native trace and finalizer checkpoint

`native_acquisition.capture` now seals original `trace.jsonl` and `video_frames.jsonl` at the 900-frame capture boundary, with hashes in `native-receipt.json`. `saved_audit.audit_native_acquisition` reopens both files and rejects changed hashes, frame identities, time joins or ego position, height, heading and speed differences from original actor packets. The trace carries the runtime's source-derived `position_m` field for physical progress checks. `analysis.finalize_native_outputs` verifies these sealed files instead of rewriting them, then writes five 20 Hz evidence channels, two context records and a Native result with explicit target and completion fields. The CPU finalizer test uses synthetic original actor packets and does not claim real CARLA movement or pixels.

`saved_media.encode_original_cameras` now also retains four root view names required by the runtime saved-video composer; each copy is byte-identical to its independently decoded FFV1 source. The full 42-test assignment suite passed in `cpu-semantic-tests.log`, all eight rebuilt exact offline constructions passed in `cpu-semantic-offline-*.log`, canonical semantic validation passed six stages and eight selected cases, and scoped static passed. `result.json` binds the current log hashes. The exact scoped strict check still rejects the truthful partial status.

Next CPU work is exact generated fixture/source packets and positive/missing-source package compatibility through Core and final video, followed by source-bound saved delivery/comparison receipts and a physical fallback plan for each selected case. Original site, access and camera sources still need worker review and binding; no legal verdict or visibility acceptance is asserted.

## 2026-11-24 first selected compatibility construction

The first selected case, `person_north_early`, now has `fixture-recipe-person_north_early.json` with 11 explicitly hashed diagnostic source files and `fixture-generator-person_north_early.json` with eight 900-frame synthetic FFV1 views. Every retained source file is below 2 MiB. The selected manifest references that exact recipe. Its provenance says diagnostic synthetic fixture; it is not an original physical or public-access source.

Official `runtime.py compatibility` materialized the source inventory, composed the required 1920x1080 overview and three 1280x720 detail views, ran the selected `analysis.py`, validated the source-derived Native result and complete video inputs, then reached Core conversion. Core requires a `capture/evidence.jsonl` projection; it is not authored yet. `cpu-compatibility-core-gap.log` records the exact attempt and missing path. This is the next CPU construction step, not a dependency failure. No compatibility receipt was claimed or entered in the selected manifest.

The Core join contract also requires source-measured `speed_mph` and 3D `position_m` on each original trace row. Capture, saved audit and finalization now retain both alongside the Native trace fields. All eight constructions were rebuilt and passed offline again, and the 42-test suite passed after this change. The diagnostic recipe source hashes were refreshed from the same source-shaped 900-frame fixture.

## 2026-11-24 first complete selected diagnostic compatibility receipt

`native_runner.py` now opens the pinned `PipelineCapture` during an actual client-backed CARLA attempt and calls it after each of the 900 original ticks. The sealed trace is the same `PipelineCapture` trace that Core consumes, with original Native actor/control/camera packets independently rejoined by `saved_audit` and `analysis`. The CPU fake-Pipeline test confirms one capture per frame and a confirmed close before actor cleanup. Actual CARLA capture and pixels have not been run or accepted.

For `person_north_early`, `build_compat_capture.py` now projects the sealed synthetic Native fixture into 900 same-frame source-hashed `capture/evidence.jsonl` and `capture/native/frames.jsonl` records, a diagnostic capture manifest and 900 generated JSON graphs. It binds numeric synthetic actor IDs, a diagnostic OpenDRIVE source, synthetic body envelopes and velocity/control fields. Every source and generator file under `work/` is below 2 MiB. The fixture provenance explicitly labels this as diagnostic synthetic material; its graph, body envelope, road and black videos are not physical observations.

Official `runtime.py compatibility` v14 passed selected analysis, Native result and four-view checks, Core conversion, Lean `adapterCheck`, saved video rendering, full video decode, selected measurement checks and the specified negative test removing `access-source.txt`. The resulting `receipt-compat-person_north_early.json`, zero-byte `analysis-compat-person_north_early.log` and `negative-person_north_early.log` are pinned in the selected manifest. Direct `check_receipts` re-materialized that fixture and independently verified the first selected receipt (`cpu-first-compatibility-receipt-check.log`). Seven selected cases still need their own case-specific diagnostic positive/negative receipts. Independent saved delivery/comparison receipts and original physical source review also remain incomplete, so `result.json` stays partial.

All eight rebuilt exact offline constructions passed the v7 command, the assignment suite passed 43 tests, canonical semantic validation passed six stages and eight selected cases, and scoped static passed again after the first compatibility receipt and result ledger refresh. The exact scoped strict command still exits 1 because preparation remains partial. No full delivery readiness is claimed.
