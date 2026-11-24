# testing__C10301__NRS-484B-600-1e__motor_vehicle_driver

## 2026-11-24 pinned capture dispatch integration checkpoint

- The three exact bundle runners now accept `runtime.py capture`'s actual `--output-dir --host --port` launch shape. The operator supplies `SCENARIO_SITE_PACKET`, `SCENARIO_NATIVE_RUN_ID` and `SCENARIO_SPEED_UNCERTAINTY_MPS`; the runner still requires a case-matched nondiagnostic site packet and route/access-aisle source references before lazy CARLA import. It allows the pinned runtime's already materialized implementation/configuration files in the attempt directory, while refusing pre-existing Native site, motion, speed, frame-map or capture artifacts. This closes the previous always-fail dispatch path without accepting a prior acquisition overwrite.
- The bundled mocked-live test exercises that exact argument/env shape against a materialized directory and checks capture call binding and prior-acquisition refusal. All three rebuilt exact constructions pass pinned `runtime.py offline`; pinned CPU preflight, 32 focused tests and scoped static pass. Exact scoped strict exits 1 on truthful partial. Commands and SHA256 logs are in `result.json.tests`.
- CPU work remains independent source review of the frozen accepted originals and actual C10301 route/access-aisle authority, canonical manifest, positive/negative compatibility and saved-delivery receipts. Physical speed, camera scene content and public-way applicability are unverified.

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.600(1)(e) — It is unlawful for any person to drive or operate a vehicle of any kind or character at: In any event, a rate of speed greater than 80 miles per hour.
Assigned branch(es): Unconditional restriction during qualifying operation..
Cell: C10301 (alley, travel, access_aisle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 3. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU boundary construction checkpoint

The exact NRS 484B.600(1)(e) restriction is greater than 80 mph. `case-plan.json` now records the three exact `__below`, `__equal`, and `__above` case IDs and controlled `strict_rate_boundary` comparison. The middle case ID follows the frozen accepted membership name; its intended 80 mph target follows the frozen accepted review, but does not claim observed 80 mph equality. Frozen review context reports sampled maxima of 74.95, 79.73, and 80.70 mph for the prior accepted recordings. Those are summary claims only: the original trace/video is absent here, between-sample peaks are unknown, and the 79.73 mph result does not demonstrate equality. Retain those accepted recordings and review their originals before selecting any duplicate capture.

`speed_capture.py:write_original_speed` writes 900 sequential 20 Hz original speed samples and a SHA-256 descriptor once per attempt. `speed_boundary.py:measure` reads that source, rejects missing/stale/noncanonical frame streams, converts SI speed to mph, preserves sample uncertainty, and leaves legal/physical acceptance unresolved. `speed_boundary.py:compare` checks three distinct Native run IDs, fixed authored setup, the declared speed-only target difference, and observed sampled speed ordering. It rejects metadata-only comparison attempts. `tests/test_speed_boundary.py` covers the positive fixture path and missing source, altered hash, malformed descriptor, changed fixed setup, missing case, duplicate run, nonsequential frames and write-once behavior. Synthetic fixtures exercise software only.

Proofs: `.venv-cpu/bin/python runtime.py preflight` passed in `.runtime-work/c10301-preflight.log`; `.venv-cpu/bin/python worker_check.py --updates` returned version 0, no pause. The five focused tests pass in `cpu-speed-boundary-tests.log`. `.venv-cpu/bin/python worker_check.py --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --complete` passes in `cpu-static-check.log`. The same command with `--require-delivery-ready` fails in `cpu-strict-check.log` because status is truthfully partial.

Next CPU work: connect the source writer to a lazy CARLA runner with actual cell geometry, actor identity and source-bound conditions; finalize exact-case measurement contracts, diagnostic recipes and positive/negative compatibility proofs; build canonical proposals, saved-only automation, independent delivery and comparison audits; then rerun the exact strict gate. The 80 mph observation, public-way applicability and actual visibility remain unverified until original physical evidence is reviewed. No legal verdict is claimed.

## 2026-11-24 Native motion checkpoint

`native_motion.py:capture_speed` is a lazy CARLA-facing 900-tick acquisition loop for the exact below/equal/above case IDs. It requires a synchronous 20 Hz world, observed ego velocity/position, a reviewed speed uncertainty input, and a caller-supplied route/camera capture; it writes original speed once through `speed_capture.py`. It rejects frame gaps, clock drift and stalled travel, records a source-hashed motion receipt, and applies full brake on success or failure. It does not claim route/site suitability or physical/legal acceptance. Eight focused tests pass in `cpu-native-motion-tests.log` (SHA256 513d31d273683f09ce44c64e4dec3b2d624352ce969ce6dd697e89608c2eb2cd).

Next: integrate this controller with a reviewed C10301 route and four-camera Native capture; seal authored site/vehicle context, add per-case saved finalization and exact compatibility receipts, then independent delivery/media audit and canonical proposals. Existing accepted summaries remain insufficient to prove 80 mph equality or public-way status.

`saved_speed.py:process` now reads only the original motion receipt and sealed speed source. Default delivery processing rejects diagnostic fixtures; the CPU fake-path test explicitly opts into diagnostic mode, verifies source/receipt joins, and rejects a tampered source hash. No CPU fake is represented as physical Native evidence. Current eight-test log SHA256: 5ce82127d006600a26d564a3684318e539dd363c31b5a0cceb632af047337c04.

`proposals/cases.json` now drafts all three exact numeric-boundary cases with unchanged C10301 cell/actor, the frozen accepted recording IDs, speed-only deliberate difference, original speed and operation-context channels, and explicit unresolved physical/legal calls. It is a draft cases proposal only; other canonical semantic stage proposals, exact site sources, bundles and proof receipts remain.

## 2026-11-24 saved-source integrity audit

`delivery_audit.py:audit_integrity` independently verifies exact-case capture-index identity, hash-bound Native motion receipt and speed source, 900 ordered original frame/camera joins, four sealed camera references, and path containment. It rejects missing media, changed bytes, invalid source paths and diagnostic fixtures in delivery mode. Its result marks `full_video_decode`, `actual_pixels` and `physical_completion` false; this does not replace canonical source-decode or physical acceptance. Nine focused CPU tests pass in `cpu-native-motion-tests.log` (SHA256 0aef090cf21f94e57453bd019e9cb7a4713f22884f09a435973a0c3d55d274ea). Reviewed route/camera capture, actual decode receipt, semantic stages, exact bundles and compatibility remain CPU work.

Each exact below/equal/above case now records its own physical-risk assessment in `case-plan.json`: an 80 mph class target over 45 seconds may exceed available alley length and clearance, and the marked access aisle must be source-verified and outside the travel path. Existing accepted original recordings must be reviewed before selecting a new capture. No invented alley geometry or physical-speed success is claimed.
After the per-case risk update, the nine-test suite was rerun; current `cpu-native-motion-tests.log` SHA256 is a831bf896e2d6e737e95e39218dd6a7086f3c54a853d3a55d6e32deb3a8bff56.

`measurement-contract.json` now maps operation, strict 80 mph speed and qualifying route/context to original saved sources, 20 Hz sampling, source-integrity audit, fixed comparison factors and unresolved legal/physical calls. It records the full-decode and pixel review gap rather than treating hashed media as decoded evidence.

`capture_finalizer.py:finalize_capture` now takes actual supplied four-camera media and 900 original camera frame readbacks after Native exit, rejects any mismatch with the original speed frame origin or run identity, and writes the source index/frame map once for `delivery_audit.py`. Ten focused CPU tests pass; current `cpu-native-motion-tests.log` SHA256 e43d03ad523adbf5155329a967f46e9e4dce2aca52868d34453f84f0ec405d48. The fake camera bytes in the test are diagnostic and explicitly fail full-video-decode and pixel acceptance. A reviewed route and real camera capture still need integration.

`native_motion.py:capture_speed` can now accept an original per-tick four-camera frame readback callback, reject nonmatching camera frame IDs, and seal `camera-frame-readback.json` into its Native receipt. `capture_finalizer.py` and `delivery_audit.py` independently reopen the readback hash and compare it with the 900-frame map. Eleven focused CPU tests pass; current `cpu-native-motion-tests.log` SHA256 3fc70956f2d7a7908d8c71c7ccc10a6a5a3321639f17b3f3383eb74e179115e5. The callback must be bound to real Native sensors in the exact runner; fixture data does not prove video pixels or physical completion.

The Native capture path now rejects any pre-existing speed source, descriptor, motion receipt or camera readback before the first world tick. A four-artifact negative test verifies no motion and preservation of original bytes. Twelve focused tests pass; current cpu-native-motion-tests.log SHA256 268ceee58d7c53c81d32acedc36e4f40629961458c3b52d561877042667630eb. Assignment static check passes; exact strict still rejects truthful partial status.

## 2026-11-24 full saved-media decode checkpoint

`delivery_audit.py:audit_decoded_media` first revalidates the sealed original speed, motion and four camera bindings, then probes each lossless video for positive dimensions, 20 Hz and exactly 900 frames, and runs an error-fatal full FFmpeg decode. It explicitly returns `actual_pixels: false` and `physical_completion: false`: decoding a synthetic or future saved stream is not a scene-content or legal-visibility judgment. A focused positive test uses a four-camera FFV1 diagnostic fixture; a negative test reseals an 899-frame camera stream and verifies frame-count rejection. Hash tampering remains rejected before decode. Thirteen focused tests pass in `cpu-native-motion-tests.log` (SHA256 c37a7015d272f4e7fa97243c422a09d9a91c1abf153ed6fa70234ae6ee29ca56). Scoped static passes; exact strict still fails because the package remains partial.

Next CPU work: review a source-bound C10301 route, integrate actor/camera spawning and route policy, finish all exact per-case bundles and positive/negative compatibility receipts, canonical semantic stages, and saved-only processing with this decoder; independently review frozen originals before new capture selection.

`saved_speed.py:process_delivery` now joins the original speed measurement with the independent four-camera full decode before writing one saved result. It rejects a pre-existing output, a resealed short video and media/speed run mismatch, and leaves no output after a failed audit. The measurement contract names the full decode. Thirteen focused tests pass (current log SHA256 99e1cb35a3c482979c2ecfab66dcf95ecaadb17e4fc586bd79db19e36c4a7ba3); assignment static passes and exact strict fails on truthful partial status.

## 2026-11-24 saved-delivery CLI and comparison identity checkpoint

`saved_speed.py` now runs `process_delivery` from its CLI, so saved processing requires source-bound speed plus four fully decoded 900-frame lossless camera streams. Delivery mode rejects a missing original camera readback; `--allow-diagnostic` is explicit for CPU fixtures. `speed_boundary.compare` requires the exact below/equal/above case order and C10301 motor vehicle driver, alley, access aisle and travel identity even if all three authored setups were consistently wrong. The CLI positive/negative and wrong-cell paths pass among 14 focused CPU tests in `cpu-saved-delivery-cli-tests.log` (SHA256 3251985b4f0be34bde08babf8b328fef0c3c10c62d77dd6802fa77472ddb1a7d). Synthetic media proves software checks only. Exact route/sensor integration, canonical stage proposals, case bundles and compatibility remain CPU work.
Scoped static check passed in `cpu-saved-delivery-static.log`; exact strict check failed on truthful partial status in `cpu-saved-delivery-strict.log`. No delivery-ready claim is made.

## 2026-11-23 source-bound case probe and receipt checkpoint

`speed_boundary.measure` now emits a case-specific one-second post-startup witness from the 900 sealed original speed samples. Below requires a wholly below-boundary uncertainty interval, equal requires an interval containing 80 mph, and above requires a wholly above-boundary interval. The frozen accepted equal summary at 79.73 mph is explicitly not promoted to equality. This is a sampled engineering probe; between-sample peaks and legal applicability remain unresolved. `saved_speed.py:process_delivery` includes the witness in its source-bound measurement.

`delivery_audit.py:audit_integrity` now rejects a hash-resealed Native motion receipt with a wrong format, fewer than 900 samples, under 100 m of observed travel, or a claimed physical acceptance. The positive four-camera decode path and three resealed-receipt negative paths pass among 14 focused CPU tests. Test log SHA256: `09020775836519243caabdf225a2cc1af1086d1f284347d8020e7d7d5ae84dda`. Scoped static passes (SHA256 `689b0c16c8ce2415edcdf21fb4575e2fc55702f635f5cb7745833e9602528bd5`); exact strict exits 1 on truthful partial status (SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: construct source-reviewed exact C10301 route, actor and four-camera sensor bindings; produce per-case canonical bundles, pinned positive/negative compatibility receipts, semantic proposals and canonical saved-process integration. No real Native pixels or physical speed probe has been accepted.

## 2026-11-23 Native site construction checkpoint

`native_site.py:construct` now binds a supplied exact-case C10301 site packet to the loaded Native map by OpenDRIVE SHA256, map name, 1.8 km continuous same-lane route and loaded-map centerline proximity. It requires source references for the access aisle and route, resolves a declared vehicle blueprint, and spawns the ego actor plus the four named RGB cameras. Failed camera spawning destroys every actor created in that attempt; the returned `NativeSite.close` cleans up a complete construction. The package does not yet contain a reviewed real site packet or claim that the map is a qualifying public way.

Nineteen focused CPU tests pass, including five diagnostic Native site tests (`cpu-native-site-tests.log`, SHA256 `d2e42742f594d7e46d4993a2943ec7eac94d091dcb9d3bf39ce3fdfed36f1d4d`). Pinned CPU preflight passes (`cpu-native-site-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Scoped static exits 0 (`cpu-native-site-static.log`, SHA256 `689b0c16c8ce2415edcdf21fb4575e2fc55702f635f5cb7745833e9602528bd5`); exact scoped strict exits 1 on truthful partial (`cpu-native-site-strict.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: review and bind a real route/access-aisle source and actor blueprint, connect four sensor callbacks/media writing to the 900-tick speed capture/finalizer, then build exact case bundles, compatibility receipts, canonical semantic proposals and process-saved integration. Diagnostic fixtures prove software construction and cleanup only.

## 2026-11-23 synchronized Native media construction checkpoint

`native_site.py` now sets the pinned four-camera profile on each spawned RGB sensor: 1920×1080 front, three 1280×720 detail views, and 0.05-second sensor ticks. `native_media.py` subscribes to all four original sensors, requires the world tick and camera frame IDs to match in sequence, checks original BGRA payload lengths, and writes each stream to a lossless FFV1 container. A bounded callback queue rejects overflow; a missing or mis-sized frame rejects capture. `native_capture.py` joins source-gated site construction, 900-tick speed control, synchronized media writing, and `capture_finalizer.py`, with sensor, writer, actor and braking cleanup on failure. It rejects a mismatch between the site packet's diagnostic provenance and the requested capture mode.

The new integration fixture executes all 900 ticks, four actual FFmpeg writers, finalization, independent full media decode and saved-only delivery processing. A missing rear camera frame fails before finalization and leaves the ego braked and every spawned actor destroyed. The fixture uses a synthetic diagnostic map and 4×4 pixels, so it proves the software join and cleanup only. The exact C10301 original site, public-way/aisle authority, physical speeds, semantic stage proposals, per-case canonical bundles and pinned positive/negative compatibility receipts remain CPU work. No new recording is selected until the frozen accepted originals are reviewed.

`native_capture.py` also seals the unchanged source site packet into the saved attempt before the first tick. The finalizer binds its SHA-256 in `capture-index.json`, and the independent saved audit requires that binding for delivery, checks exact case/cell/actor/maneuver identity, and rejects changed bytes. The integrated diagnostic test verifies the positive join and the changed-byte rejection. This is a source-integrity proof, not certification of the packet's real-world map or aisle claims.

`speed_boundary.compare` now checks the sealed original site packet for every exact case when a capture index exists, requires it for delivery attempts, and compares all fixed site content after excluding only the case ID. A negative test first changes an original site packet without rehashing, then rehashes a changed route to prove the fixed-condition check still rejects it. The authored requested-speed triple and measured speed ordering remain separate checks. Twenty-five focused tests pass.

## 2026-11-23 original route readback checkpoint

`NativeSite.observe_route` projects each actual actor transform to the reviewed route polyline, reads the loaded Native waypoint lane, and rejects an offset greater than 2 m, wrong lane, or reversed station. This 2 m corridor is an engineering capture guard, not a legal boundary. `native_capture.py` passes it to `native_motion.py`, which seals 900 original frame/route samples in `route-frame-readback.json` and the motion receipt. `delivery_audit.py:audit_integrity` independently rejoins every route row to the original frame map, requires consistent lane and at least 100 m route progress, and rejects changed bytes and rehashed off-route samples. `measurement-contract.json` and `case-plan.json.native_route_readback` name these sources and limits.

The 26-test focused suite and pinned preflight pass in `cpu-route-readback-tests.log` and `cpu-route-readback-preflight.log`. Tests cover projected station, centerline, lane and reverse negatives plus an integrated 900-frame capture and rehashed off-route saved-audit rejection. Diagnostic map/pixels remain synthetic; physical speed, public-way/access-aisle applicability and accepted-recording source review remain unresolved. Canonical per-case bundles, semantic proposals and pinned compatibility receipts are still CPU work. The package remains partial until the exact strict gate passes.

## 2026-11-23 operator-owned world lifecycle checkpoint

`owned_capture.py:capture_owned` wraps the existing exact C10301 Native site, speed, camera and finalization path. It snapshots the supplied operator-owned client, applies synchronous 20 Hz settings, rejects a failed settings readback before actor spawn, and calls the pinned `world_restore.restore` with map/OpenDRIVE, settings and weather readback after both successful capture and a missing-camera failure. It never allocates a server or treats the diagnostic map as a reviewed C10301 route. The success test executes all 900 ticks and four FFV1 writers; failures prove actor/sensor cleanup and world restoration.

Pinned preflight, 29 focused CPU tests and scoped static check pass in `cpu-owned-capture-*.log`; the exact scoped strict gate exits 1 on truthful partial status. Commands and SHA256 receipts are in `result.json`. Remaining CPU work is original accepted-evidence and route/access-aisle authority review, exact canonical bundles, remaining semantic proposals and positive/negative compatibility plus saved-process proofs. Actual physical speed, road applicability and camera scene content remain unresolved.

## 2026-11-23 exact-law semantic stages checkpoint

Added `proposals/semantic-index.json` and all five canonical stage families: relevance batch/relevance, template, bindings, existing exact cases and three judgment-observable proposals. Every index digest binds the proposal bytes, and the input assignment quote and SHA bind the 80 mph strict upper boundary. The proposals keep actor, territorial applicability, sampled equality and between-sample speed unresolved. The focused suite now passes 31 tests, including exact-source/hash and three-case boundary assertions. Pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful `partial`; original accepted-source review, actual C10301 route/access-aisle authority, canonical case bundles, positive/negative compatibility and saved processing remain.

Current semantic CPU log SHA-256 receipts:

- `cpu-semantic-tests.log`: `6511a949e6d3cd09d6f7b5b42be8286afb0b604c3714ea3f04b27a61ea50db5a` (exit 0)
- `cpu-semantic-preflight.log`: `fd09414ca75cf10707b0cdc0fd2c663162f55b3257ea4f39eabbff891e762776` (exit 0)
- `cpu-semantic-static.log`: `689b0c16c8ce2415edcdf21fb4575e2fc55702f635f5cb7745833e9602528bd5` (exit 0)
- `cpu-semantic-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

## 2026-11-23 three exact source-gated offline bundles

`build_offline_draft.py` now packages the existing Native site, 900-tick motion, four-camera media, finalizer and independent audit modules into the exact below/equal/above speed constructions. The runner checks the source plan SHA, exact case and requested 75/80/85 mph values, original clock and camera profile. It refuses a Native run without a reviewed C10301 route, access-aisle authority and site packet. Each bundle includes a CPU test for source binding and that refusal. These are diagnostic-only constructions and do not replace source review of the three frozen accepted originals.

All three exact offline materializations, 32 focused tests, pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. Canonical production bundles, positive/negative compatibility, saved delivery and source review remain.

- `cpu-bundles-build.log` SHA256 `63e8bfb6d5fdd1a59d7ec4dcc5c033184bd023013990de8fd7cb0ac7138c65ea`; exit 0.
- `cpu-bundles-tests.log` SHA256 `1e38be082b10dbc2a57cf851c194d18b5122a4c55d56e4025ae018f1f2634089`; exit 0.
- `cpu-bundles-preflight.log` SHA256 `0ac552aa9ce1fb76103df88aa199d25778b3bc470fec7dbe9b688e72039d0bb6`; exit 0.
- `cpu-bundles-static.log` SHA256 `689b0c16c8ce2415edcdf21fb4575e2fc55702f635f5cb7745833e9602528bd5`; exit 0.
- `cpu-bundles-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; exit 1.
- `cpu-bundles-offline-below.log` SHA256 `c22474dacce594da6f90c80819093ffcc3e3a0e80e3d5122742aa025c0994dfd`; exit 0.
- `cpu-bundles-offline-equal.log` SHA256 `d03d79234caa356477ff206a3c61d4bff94ef02caaad1c7814eedce56b538aed`; exit 0.
- `cpu-bundles-offline-above.log` SHA256 `08214817da8a5b19ea71b0613d824a7a02c2b7c79b5b72c0c36de6fb3effa0c7`; exit 0.

## 2026-11-24 source-gated Native bundle entrypoint

`build_offline_draft.py` SHA256 `ea49b2ee8ba8130c6185f2b2b59e4b8d1243e8f9cf27a9600663b8685a7c160f` now embeds an executable CARLA entrypoint in each exact below/equal/above bundle. It validates the source plan, exact case and 20 Hz/900-frame profile; a live invocation requires a case-matched nondiagnostic site packet with route and access-aisle source references, fresh output, run ID and speed uncertainty. CARLA is imported lazily after those guards. The entrypoint delegates capture, four-camera synchronization, cleanup and operator-owned world restoration to `owned_capture.capture_owned`. The CPU positive uses a mocked client and capture call; it does not certify source references or launch CARLA.

The focused suite passes 32 tests (`cpu-live-tests.log` SHA256 `63441f5db101d12aa4130347184ecb87b67b135a297cda443534d0da9e52da8f`). All three rebuilt exact bundles pass pinned offline, and pinned preflight plus scoped static pass; exact scoped strict exits 1 on truthful partial. Log hashes and commands are recorded in `result.json`. Next CPU work: independently review frozen accepted originals and a real route/access-aisle site source, then produce source-hashed positive/negative compatibility, canonical manifest and saved-delivery receipts. Physical speed, actual camera pixels and territorial applicability are unverified.
