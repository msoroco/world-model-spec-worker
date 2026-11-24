# testing__C109705__NRS-484B-400-2b__motor_vehicle_driver

Status: partial exact case plan with source-bound geometry, pair audit and lazy route policy. Four existing-recording case identities are mapped; no new recording is selected.

Exact law: NRS 484B.400(2)(b) — If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: After entering the intersection, the left turn must be made so as to leave the intersection to the right of the centerline of the highway being entered.
Assigned branch(es): Two-directional intersection within the general intersection layout..
Cell: C109705 (intersection, left_turn, centerline); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 4. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. The four exact prior-setting cases and two controlled comparisons are mapped. Bind them to original trace/map/video sources when available; no judgment-range entry applies to this law/actor.
3. Complete the source-survey route policy with actual Native spawn/capture and CPU test; author case-specific finalization, semantic proposals, diagnostic recipes, saved-only processing, delivery receipts and risk-based fallback assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## Exact departure construction checkpoint (2026-11-23)

The four exact prior setting IDs now appear in `case-plan.json.cases`: `near_centerline`, `farther_from_centerline`, `imaginary_near_centerline`, and `imaginary_farther_from_centerline`. They map to the four frozen accepted recording IDs, with two controlled comparisons: `departure_lateral_position` and `imaginary_departure_lateral_position`. Each pair fixes the connected two-directional left-turn approach, 45-second four-camera contract and its own centerline convention, varying only the requested departure lateral position. These are source-review and construction targets; original trace and video are absent from this export, so no new recording is selected or existing recording claimed sufficient.

`departure_geometry.py` is an executable saved-source measurement: it verifies case/road connection, driver control, two-directional highway context, source-identified mapped or imaginary destination centerline, original intersection-entry ordering and full-body departure corners. It projects every corner onto the destination direction's right normal, retains per-frame and overall extrema, and leaves statutory position judgment null. `comparison_audit.py` independently checks source hashes, case IDs, common map source, distinct trace sources, connected roads, centerline convention and observed ordering. It rejects a legal label; shared map and ordering alone do not establish identical approach motion or legal compliance. Both scripts have CLIs for eventual original source packets.

`cpu-departure-tests.log` (SHA256 `7a5b91ebcc24da168f250051d20a70d871e24252bb3b7f3eb5d283186713e8b3`) records 13 passing CPU tests for right-side projection under both directions, missing context/body/road, source tampering, invalid comparison context, unrealized difference and leaked legal labels; plus map opposition, connection, imaginary-line source, source map hash, pair isolation and bounded route control. Run with `.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v`. Pinned `.venv-cpu/bin/python runtime.py preflight` passed on this host.

Next CPU work: make an exact lazy CARLA/Native construction and original-map readback for all four cases, bind finalization to the exported original source packets, author canonical semantic proposals and four case diagnostic recipes, run exact offline and positive/negative compatibility, saved-only and independent delivery proofs, and bind the per-pair comparison audit. The original accepted metadata is insufficient to claim either comparison physically established; preserve its uncertainty and do not set `ready` until the assignment's exact strict gate passes.

`construction.py` now defines the four exact departure targets from an original source-hashed Native map survey. It checks two opposed permitted lanes on each sourced non-alley highway, connected approach/destination road IDs, marked or derived imaginary destination centerline, waypoint route, vehicle blueprint and camera plan. The pair shares its approach and controller policy; engineering lateral targets are 1.7 m and 2.7 m, never statutory cutoffs. Its bounded waypoint controller can be exercised on CPU. This is a route policy awaiting a surveyed map and Native actor/camera/capture implementation, not a claimed physical construction.

## Native capture adapter checkpoint (2026-11-24)

`native_capture.py` is a lazy adapter loop for all four exact case IDs. The caller supplies a reviewed, source-hashed map survey and an adapter implementing Native ego spawn, synchronized camera setup, waypoint readback, control, tick, ego snapshot, original camera-frame indexing, emergency stop and actor cleanup. The loop records 900 consecutive 20 Hz frames over 45 seconds. It requires per-frame case identity, full body corners, measured pose and speed, observed entry before connected-road departure, driver control, and all four synchronized original camera source references. It writes source-hashed original trace and camera index packets for saved processing. These are adapter contracts; no CARLA run or physical acceptance is claimed by the CPU tests.

`cpu-departure-tests.log` now records 17 passing tests (SHA256 `7bb5e97a48fa3975a086477424a439cec3d507453da090f34f8c93771c2b8625`) including fake-adapter positive 900-frame capture and negative missing-camera, missing-entry and frame-gap cases with guaranteed emergency stop and cleanup. Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v`.

Remaining CPU work includes a concrete CARLA adapter and reviewed map survey, saved-source verification of each original camera file and map packet, case-specific finalizer, semantic proposals, four exact offline and positive/negative compatibility proofs, saved-only and delivery audits. Keep the four accepted recordings at metadata-review status until original packets are available and audited.

Exact scoped `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete` passed (`cpu-static-check.log`, SHA256 `f0d299bf832c8d5b5ee6d6d81443685e167d1689691b6302ca03ca933643e8b9`). The same command with `--require-delivery-ready` correctly failed while status is partial (`cpu-strict-check.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). The 14 returned files in this assignment are UTF-8 text under 2 MiB with no trailing whitespace or conflict markers.

## Saved source and loaded-map checkpoint (2026-11-24)

`saved_delivery.py` now independently verifies the exact four case identities against an attempt-local manifest, source hashes and paths for the original map, map packet, trace packet and four camera index packets. It requires 900 consecutive original 20 Hz trace frames over 45 seconds, checks the destination centerline convention for each exact case, runs the source-bound full-body departure measurement and verifies each retained camera source file hash with exact frame and channel joins. It rejects diagnostic acquisition for delivery unless a test explicitly opts in. The diagnostic fixture still reports `full_video_decode: false`, `actual_pixels: false`, `physical_completion: false` and no statutory-position judgment. This source-byte audit does not replace the pinned video decoder, real camera visibility review or a sealed Native delivery receipt.

`native_map.py` checks a loaded CARLA map's name and full OpenDRIVE SHA256 against the reviewed survey packet before building an exact route plan. It remains a lazy interface, so CPU fake-world tests prove the readback and rejection logic only. The source survey's public-highway annotation must still be independently reviewed against original material. `construction.py` now rejects nested case IDs that merely end in a valid suffix; only the four exact case IDs are admitted. The saved audit rejects one source file aliased across different camera channels.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v`. The refreshed `cpu-departure-tests.log` records 26 passing focused tests. `.venv-cpu/bin/python runtime.py preflight` passed and is retained in `cpu-preflight.log`. The assignment-scoped `worker_check.py --complete` passed in `cpu-static-check.log`; the exact `--complete --require-delivery-ready` command remains exit 1 in `cpu-strict-check.log` because this package truthfully remains partial. Current log hashes are in `result.json` for the test and preflight claims.

Next CPU work: author the concrete CARLA adapter and case finalizer, reviewed original survey/acquisition packets, canonical semantic proposals, all four exact offline and positive/negative compatibility receipts, saved-only processing fixtures, independent video/decode delivery receipts and source-backed comparison proofs. Accepted metadata cannot prove the centerline, route or actual video coverage. Keep this assignment partial until the exact strict gate passes.

## Saved-only finalization checkpoint (2026-11-24)

`finalize.py` now calls the independent `saved_delivery.py` audit before creating an output file. It records exact case and source-manifest hash, 900-frame coverage and per-frame full-body signed destination-centerline ranges, with a null statutory judgment. It reports pixel decode, participant coverage and physical completion as unverified. A saved report is created exclusively after all required source hashes, centerline context and camera joins pass; an existing report is never overwritten. Positive and negative CPU fixtures test successful diagnostic finalization, refusal of diagnostic delivery, stale retained media and existing-output refusal. The complete focused suite now passes 28 tests (`cpu-departure-tests.log`, hash in `result.json`). This is a case-specific saved measurement stage; pinned `runtime.py process-saved` and complete delivery auditing are still outstanding. Scoped static remains exit 0 and scoped strict remains exit 1 on truthful partial status.

## Full original PNG source decode checkpoint (2026-11-24)

`saved_pixels.py` decodes every indexed original PNG file for the four camera channels and 900 consecutive Native ticks. It binds each frame and channel to its SHA256, forbids a reused file within one stream, requires RGB/RGBA PNG, fully loads image pixels and checks fixed per-channel dimensions. For original Native delivery, the saved audit now requires `camera_media_kind: original_png_frames` and enforces the capture profile: dash 1920x1080; front/left/right 1280x720. Diagnostic fixtures may use smaller images. The saved report sets `full_source_decode` and `actual_pixels` only after decode; it still leaves full composed-video decoding, participant visibility, physical completion and statutory judgment unverified.

The focused suite uses 3,600 separate small PNG files and verifies complete decode, mismatched delivery profile rejection and stale-image rejection. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v` passed 30 tests in `cpu-departure-tests.log`. Pinned `runtime.py preflight` and assignment-scoped static check passed. The exact strict check remains partial. Next CPU work: concrete CARLA adapter and reviewed map survey; original media/trace receipts; canonical proposals; four exact offline/compatibility bundles; process-saved and independent delivery proof.

## 2026-11-23 four-case diagnostic bundle checkpoint

`build_offline_draft.py` binds the four exact accepted-setting case identities to a source-hashed plan, mapped versus source-derived imaginary destination centerline, near/far engineering departure targets and the 20-Hz/900-frame/four-camera capture profile. Each inline construction embeds current route policy, lazy Native capture, saved full-body departure measurement, original PNG decode, finalization and comparison audit. The bundled runner checks exact identity and refuses an unsourced Native launch. All four pinned `runtime.py offline` checks passed with materializations under `.runtime-work/`; the 31-test focused suite and pinned preflight passed. These are diagnostic reproduction drafts and do not replace the four accepted recordings or claim their original source availability.

Proof SHA-256 (logs under this assignment):

- `cpu-departure-tests.log`: `becb84a98032e6f94aca92ddda73a170fe0ec7da739bd183ca2328b8db4b9acf` (exit 0)
- `cpu-preflight.log`: `0bb4d88702b636d21befbc514f736402247799402455553f8f3536dc7dd85534` (exit 0)
- `cpu-static-check.log`: `f0d299bf832c8d5b5ee6d6d81443685e167d1689691b6302ca03ca933643e8b9` (exit 0)
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-near_centerline.log`: `77487d9576d7d5ecf736c71fc52ae9f34108055ae2e46a49e5c7155f94f3d054` (exit 0)
- `cpu-offline-farther_from_centerline.log`: `571cc96012c4d9e116835d559af623e269bf0e7d3acfc04690fee2f3f15f6a83` (exit 0)
- `cpu-offline-imaginary_near_centerline.log`: `97e5dbbcdc3f000148b5b8c898b5042790225b8d21b3784d065f3bf6ff2528d6` (exit 0)
- `cpu-offline-imaginary_farther_from_centerline.log`: `d14cccddbd2da0d59747ca6d73b7eb44f4b9525f6a4cfee4fef9f7cca334cea4` (exit 0)

Next CPU work: bind reviewed original map/survey, trace and camera packets to the accepted IDs or a separately reviewed Native execution; author canonical semantic proposals and manifest; run source-shaped positive/negative compatibility, pinned saved-only processing and independent delivery/comparison receipts for each case. The accepted export contains metadata but not the physical source packets, so no measured centerline or video conclusion follows. Scoped strict fails on truthful `partial` status.

## 2026-11-23 departure route-order invariant

`native_capture.py` now rejects turning before an observed intersection entry and any return to an approach, entry or turning phase after destination-road departure. `departure_geometry.py` independently rejects the same source-trace regressions in saved measurement. New negative CPU tests exercise early turn, post-departure turn and repeated entry, including Native ego cleanup. All four inline diagnostic constructions were regenerated to embed current code. This enforces the statutory sequence without imposing a numeric legal lateral cutoff.

Pinned preflight, bundle build, all **34** focused tests, four exact offline checks and scoped static exited 0. The exact scoped strict gate exited 1 on truthful partial status. Commands and cleaned SHA-256 log receipts are in `result.json.tests`. Next CPU work remains reviewed original map/trace/media binding, concrete CARLA adapter, canonical proposals/manifest, compatibility, saved-only processing and independent delivery receipts.

## 2026-11-23 original approach isolation and write-once capture checkpoint

`native_capture.capture` now refuses an output directory with retained original evidence and writes trace and camera-index packets exclusively. The new CPU test confirms a preexisting trace remains unchanged and no Native control is applied. `comparison_audit.audit` now opens the two SHA-bound original traces and compares the pre-entry position, heading and speed samples with declared engineering tolerances (0.25 m, 0.1 rad, 0.5 m/s). It rejects changed approach trajectory, missing entry or reused trace, while leaving the statutory departure-position judgment null. These tolerances control comparison isolation; they are not legal thresholds.

Pinned preflight, all 36 focused tests, four refreshed exact inline diagnostic constructions and four pinned offline runs passed. Scoped static passed. Exact scoped strict exited 1 because this package is truthfully partial. Current commands and SHA-256 logs are in `result.json.tests`; the rebuilt case hashes are in `execution-manifest.draft.json`. The first offline attempt used a relative `--python` path and failed inside the materialized bundle; all four were rerun successfully with an absolute interpreter path and fresh scratch outputs.

Next CPU work: source-shaped positive/negative compatibility and saved-only proofs for each exact case, a concrete CARLA adapter and source-gated original map/camera capture, canonical semantic proposals and independent delivery release. The four accepted recording metadata records do not contain original source packets, so they do not establish physical centerline or visibility coverage.

## 2026-11-24 original Native clock integrity checkpoint

`native_capture.py` now requires an original finite elapsed timestamp on every Native ego snapshot and checks the full 900-tick sequence against the 20 Hz source clock within a 2 ms acquisition tolerance. It writes those timestamps into the original trace. `saved_delivery.py` independently reopens the sealed trace and verifies all 900 elapsed timestamps against that same clock before evaluating the departure or camera sources. These are sampling-integrity tolerances, not statutory thresholds. Both capture and saved CPU tests reject a clock drift; the capture test also verifies emergency stop and actor cleanup.

All four exact diagnostic constructions were regenerated to embed the updated capture and saved auditors. The 38-test focused suite, pinned preflight, four `runtime.py offline` checks, and scoped static gate exited 0. The exact scoped strict gate exited 1 on the truthful partial status. No physical Native run or accepted-source recording was inferred.

SHA-256 bound proof logs:

- `cpu-clock-tests.log`: `466a15fe6cd190f16427465920c1360c9ba84c718cb62c162dc1f77330e05977` (exit 0)
- `cpu-clock-preflight.log`: `b823b61d9c1d2cfdafe11ad56fd052f3f7058f53f88c9183f5bd2e9b9fce7ae5` (exit 0)
- `cpu-clock-offline-near_centerline.log`: `10c0ff4f30fd08ab7752c44636d8dba0d1d3ac1a98db24c56d5a78a25f75715c` (exit 0)
- `cpu-clock-offline-farther_from_centerline.log`: `451ed9772d06b10b2e00f016348cf363eac3a192abc3f3a946e853db074e410e` (exit 0)
- `cpu-clock-offline-imaginary_near_centerline.log`: `243909baada1cab13f46ff151a82838745e58f0a32edaf34a3b18fa4c02b38f1` (exit 0)
- `cpu-clock-offline-imaginary_farther_from_centerline.log`: `1ae4699f2dab4586acd0b66165449c2fc34bbc92b1cf4e076b3c71352df4a562` (exit 0)
- `cpu-clock-static.log`: `f0d299bf832c8d5b5ee6d6d81443685e167d1689691b6302ca03ca933643e8b9` (exit 0)
- `cpu-clock-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

Next CPU actions: implement the concrete CARLA actor/camera adapter with source-reviewed map and original image acquisition, author canonical semantic proposals and manifest, source-shaped positive/negative compatibility plus process-saved receipts, and independent delivery/comparison release audits for all four exact cases. Existing accepted metadata alone does not prove its original centerline, trace, clock or media. Preserve partial until the exact scoped strict gate passes.

## 2026-11-24 saved original source path integrity

`saved_delivery._read_source` now rejects a symlink in any component of a retained original map, trace, index or camera source path before trusting a matching SHA. The negative tests rebind a trace through a symlinked file and a map packet through a symlinked directory; both are rejected. The four exact diagnostic constructions were regenerated with the current saved auditor. All 39 focused tests, pinned preflight, four pinned offline materializations and scoped static pass; the exact scoped strict gate exits 1 on truthful partial status. Commands and SHA256 receipts are in `result.json`. This protects saved source identity but does not establish a reviewed Native highway map, real camera coverage or a statutory departure-position judgment. Production adapter, canonical semantic proposals and manifest, positive/negative compatibility, saved-only processing and independent delivery/comparison receipts remain CPU work.

## 2026-11-24 original camera PNG acquisition checkpoint

`native_camera_source.py` now requires an exact SHA-bound reviewed survey packet with four named camera poses, spawns four ego-attached CARLA RGB actors at the 20 Hz capture profile, joins each original callback to its exact Native world frame, saves the callback image to a distinct attempt-local PNG and returns its SHA and path to the existing Native index. It refuses an unsurveyed pose, changed survey bytes, stale or missing callbacks, changed image dimensions and source overwrite. `native_capture.capture` accepts this owned source, verifies its output is attempt-local, uses its frame receipts, and closes all camera actors even on capture failure; ego stop and destruction remain in the cleanup path. CPU fakes test original callback PNG bytes, hash binding, sensor ownership and failure cleanup. These tests make no claim that an actual CARLA survey or recording is present.

All four exact diagnostic bundles were rebuilt to include the new acquisition adapter. `cpu-camera-tests.log` records 44 focused tests passing; `cpu-camera-preflight.log`, four `cpu-camera-offline-<case>.log` files and `cpu-camera-static.log` exit 0. The exact `cpu-camera-strict.log` exits 1 on truthful partial status. All eight logs are SHA-bound in `result.json`. Next CPU work: concrete ego and map actor adapter, canonical proposals/manifest, source-shaped compatibility and pinned saved-only processing, plus independent delivery/comparison receipts. The four accepted recording metadata entries still lack their original trace and camera files in this export; no physical or statutory conclusion follows.

## 2026-11-24 original CARLA ego adapter and production runner

`native_ego_adapter.py` now checks the reviewed survey hash and loaded OpenDRIVE hash, source-surveyed spawn and phase polygons, live map waypoint readback, actual ego body vertices, road ID, speed, control readback and original snapshot clock. `build_offline_draft.py` embeds it in all four exact constructions; the bundled runner requires a reviewed survey and map file, exclusively owns a synchronous 20 Hz CARLA world, uses `NativeCameraSource` for four original camera PNG streams, seals the acquisition receipt, and restores world settings. No unsurveyed fallback or physical acceptance is inferred.

47 focused tests (`cpu-ego-adapter-tests2.log`), four exact updated offline checks, and scoped static pass. The exact strict check exits 1 on truthful partial status (`cpu-ego-adapter-strict.log`). All command and log SHA-256 bindings are in `result.json`. The next CPU work is selected delivery manifest and canonical semantic proposals, source-shaped positive/negative compatibility and saved-only proofs, followed by independent delivery/comparison receipts. Original accepted recording media remains absent; that absence does not stop the remaining CPU work.

## 2026-11-24 original Native to saved-only source seal

`native_seal.py` now binds the exact reviewed survey SHA, original OpenDRIVE bytes and public-highway review status to the original trace/camera-index SHA receipts. It retains `original-map.xodr`, `original-map-packet.json` and `source-manifest.json` in the attempt with overwrite refusal. The production runner calls this after the source-owned CARLA capture and restores world settings. The manifest is consumable by `saved_delivery.audit`; physical completion and legal judgment remain false/unresolved.

49 focused tests (`cpu-native-seal-seal-tests.log`) and four exact updated offline bundle checks pass. Scoped static exits 0 and strict exits 1 on truthful partial status (`cpu-native-seal-seal-strict.log`). Commands and log hashes are recorded in `result.json`. Next CPU actions remain selected delivery manifest and canonical semantic chain, case-specific positive/negative compatibility and process-saved receipts, and independent delivery/comparison proof receipts. The original accepted recording files are absent in this export, so no physical claim is made.

## 2026-11-24 selected exact construction binding

`execution-manifest.json` now binds all four exact selected cases, current runtime SHA, construction hashes and passing selected-manifest offline receipts. Its `preparation_status` is explicitly `offline_only_partial`; no compatibility, saved processing or independent acceptance is claimed. `build_selected_manifest.py` reproduces these bindings after exact offline logs are present. The four `cpu-selected-offline-*.log` files pass. Scoped static passes (`cpu-selected-static.log`), and strict exits 1 on the truthful partial result (`cpu-selected-strict.log`).

Next CPU steps: author the complete canonical semantic chain and structured recording descriptions, exact measurement contracts and source-shaped recipes, run each exact positive/negative compatibility and saved-only processing, then bind physical/delivery/comparison audits. The selected package cannot be ready until its exact strict gate exits 0.

## 2026-11-24 semantic and package compatibility progression

The canonical seven-stage semantic chain validates for all four exact selected cases against the current runtime. The 52-test focused CPU suite and assignment-scoped static gate pass. Four exact primary compatibility runs passed: each tested source-bound departure analysis, negative removal of original-map-packet.json, Native result validation, Core conversion, Lean decoder, four-view rendering and final decode. Their CPU fixtures are marked diagnostic and do not substitute for the missing original accepted media.

Each exact case also has a slower Native controller fallback construction and passing fallback offline proof. Synthetic physical fixtures yielded met, not_met and unverified outcomes for all four cases; lifecycle tests verify saved processing starts after capture closure and owner release. Fallback compatibility is still executing. Saved-only processing, independent delivery and comparison audits, and top-level return bindings remain CPU work. Keep status partial until exact strict gate exits 0.
