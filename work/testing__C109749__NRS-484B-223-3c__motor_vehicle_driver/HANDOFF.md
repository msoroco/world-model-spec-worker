# testing__C109749__NRS-484B-223-3c__motor_vehicle_driver

Status: partial exact case construction. No physical recording has been made or accepted.

Exact law: NRS 484B.223(3)(c) — If a highway has been designed to provide a single center lane to be used only for turning by traffic moving in both directions, the following rules apply: A vehicle must not travel more than 50 feet in a center turn lane after making a left-hand turn onto the highway before merging with traffic.
Assigned branch(es): Intersection entry with receiving traffic.
Cell: C109749 (intersection, left_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Exact coverage and CPU construction

The selected branch has four planned cases in `case-plan.json`: `__below_50ft` (49-foot target), `__at_50ft` (50-foot target), `__above_50ft` (51-foot target), and `__no_merge` (censored observation). The first three form the numeric boundary comparison; below and no-merge form the merge-observation comparison. All require the same verified public highway, single bidirectional exclusive center turn lane, left turn onto that highway, receiving through lane and other vehicle. A commanded merge station is not a measured distance or legal outcome. There are no frozen accepted recordings for this assignment.

`center_lane_site.py::validate_site` requires a reviewed public-highway source, original Native map source, exactly one exclusive bidirectional shared center turn lane, opposing through directions and correct entry/merge targets. `center_lane_measurement.py::measure_center_lane_distance` integrates original body-centre path after the turn completion marker through the first through-lane merge marker. It rejects missing context, missing/duplicated frames, untracked lane exit and duplicate turn events. A missing merge is censored. The raw body history must remain available for reviewer resolution of vehicle reference point and event convention.

`turn_merge_controller.py::TurnMergeController` commands the entry, center-lane and through-lane waypoint route without importing CARLA until `apply`. Fake-vehicle tests exercise eastbound and westbound turns, merge-waypoint progression, steering, speed control and control application. The route must be built from an original source-gated Native site; commands are not observed travel.

`comparison_audit.py` independently checks all three original numeric measurements and the censored no-merge contrast, requiring shared site, receiving traffic, entry route and camera bindings. Negative fixture tests reject missing original traces, changed traffic, censored numeric cases and false no-merge markers.

`native_capture.py::capture_original` now writes a source-bound original 20 Hz body/lane/event trace, four-camera frame map with each original camera file SHA256, site packet and measured capture receipt. It requires reviewed highway and Native map source hashes, original contiguous frame/time identity, a single observed turn event and observed merge lane; it rejects drift, missing camera/lane readbacks, camera source byte tampering and duplicate capture. The saved delivery audit can consume this receipt directly. These tests use fixture readbacks, so source review and physical observation remain pending.

`delivery_audit.py::audit_saved_delivery` independently reopens and hashes the original trace, highway review, lane-design packet and 20 Hz frame map; it joins every original trace frame to all four camera source names and recomputes the delivered turn/merge frames and distance. Its read-only CPU tests reject a tampered trace, substituted result arithmetic, changed context source, missing camera, missing frame and path escape. This is a saved-source audit implementation, not a positive compatibility receipt or physical acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109749__NRS-484B-223-3c__motor_vehicle_driver/tests -v` passed 34 source-shaped fixture checks in `cpu-construction-tests.log` (SHA256 `df33241fbc469f6b16fe278e111e1c9aea5c3261bddaf128ce41e89e2652d9fe`). These fixtures exercise software geometry, numeric boundaries and source integrity; they are not original Native measurements.

## Next CPU actions

1. Source-gate a Native map site: original lane topology must establish the single exclusive bidirectional center turn lane and a through-lane merge; review a public-highway source. The exported cell label alone does not establish these facts.
2. Integrate the controller and new Native acquisition bridge with the exact CARLA runner and actual four-camera sensor files, then complete a saved finalizer. Keep the four target cases and source-bound reference convention; verify both road approach directions.
3. Wire the read-only delivery audit to the case-specific saved finalizer and original Native acquisition files; complete exact semantic proposals, offline and positive/negative compatibility receipts, saved-only processing and risk-based fallback only after a measurable physical risk has a tested alternative.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing CPU gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed again with the pinned CPU environment, FFmpeg and Lean. The 34 assignment fixture tests passed. These are construction and saved-source audit checks, not exact delivery proofs. CARLA is needed only after the CPU package is ready for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Current acceptance gate

The assignment-scoped static checkpoint command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-223-3c__motor_vehicle_driver --complete` passed. The same command with `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log`. Status remains partial while listed CPU deliverables are incomplete.

## 2026-11-23 saved finalizer construction

`saved_finalizer.py::finalize_saved` reopens the original fixed Native capture receipt, verifies exact case and attempt identity, rehashes and validates the site packet against original map/highway source bindings, invokes the independent saved delivery audit, requires the expected complete frame count, and checks observed merge versus the exact case branch. It returns measured distance and raw-source hashes without a legal verdict or physical acceptance claim. `tests/test_saved_finalizer.py` covers merge and censored cases plus substituted case, incomplete count, missing planned merge and changed site binding. The complete focused suite passed 37 tests in `cpu-construction-tests.log`. Scoped static passed in `cpu-static-check.log`; exact scoped strict failed on partial status in `cpu-strict-check.log`. Next CPU work: bind a complete 900-frame four-camera Native runner, original map and reviewed-highway evidence, semantic proposals, exact per-case offline/compatibility/saved-only receipts, and delivery manifest.

## 2026-11-23 synchronized sensor and saved pixel proof

`native_capture.py::sensor_frame_reader` now writes four synchronized BGRA sensor readbacks as original lossless RGB PNGs at the prospective 20 Hz profile dimensions. It rejects camera frame or dimension drift, incomplete bytes and duplicate paths before `capture_original` binds source hashes into the original frame map. `saved_camera_audit.py::audit_original_pngs` independently reopens that map and every original PNG, checks contiguous Native frame IDs, exact four-camera source paths, source hashes, PNG format, RGB mode and dimensions, and fully decodes all images. `saved_finalizer.py::finalize_saved` calls that audit and returns the decoded image count. The dimension override is only for small CPU fixtures; the default requires 1920x1080 overview and three 1280x720 detail views.

The focused suite passed 41 tests in `cpu-construction-tests.log`, including a complete 900-frame, 3,600-image fixture and hash-current malformed-camera/profile negative cases. The fixture uses 2x2 synthetic pixels and establishes the acquisition/decode software path, not physical visibility. `cpu-static-check.log` records the passing assignment checkpoint; `cpu-strict-check.log` records the exact strict command failing because status remains partial. Hashes for these logs are in `result.json`. Next CPU work remains the map/highway source review, exact CARLA runner and source-bound per-case proposal/offline/compatibility/saved-only receipts. No external blocker is asserted.

## 2026-11-24 numeric probe and merge-event checkpoint

`center_lane_measurement.py` now rejects a merge event before the measured turn completion and duplicate merge events, preventing an ambiguous first-merge distance. `comparison_audit.py` independently requires the three source-measured distances to realize below, at and above the statutory 50-foot boundary in their declared order. The at-boundary 0.25-foot tolerance is only an engineering capture probe; vehicle reference-point interpretation and legal outcome stay unresolved. The 43-test focused suite passed (`cpu-construction-tests.log`, SHA-256 `045ec9c4b926c4a03801808d179a47ab3fb0ce7964e0b36d2c89e3e130267f0d`). Original Native highway/map source review, exact runner, semantic stages and per-case offline/compatibility/saved delivery receipts remain CPU work.

## 2026-11-24 live CARLA frame-reader checkpoint

`carla_runner.py` now supplies the existing source-sealed Native capture writer with a lazy live CARLA reader. It requires synchronous 20 Hz settings and a sealed original OpenDRIVE hash matching the live map before any motion. The injected reviewed route drives `TurnMergeController`; each post-tick sample reads the Native world snapshot, eight ego body vertices, ego lane from the original waypoint, receiving vehicle waypoint lane and actor ID, and four exact-frame camera callbacks. Turn completion and merge markers arise once from observed approach-to-center and center-to-through lane transitions, not from the requested distance. The reader releases camera listeners after success or failure. The integration fixture seals a four-frame exact case and reopens its original trace; negative tests reject receiving traffic in the wrong lane and a changed live map before motion. The full suite passes 46 tests. These source-shaped fakes establish software joins, not actual lane designation, turn completion, vehicle placement or 50-foot physical measurement.

Next CPU work: source-gated actor and camera spawning with world lease and exact 900-frame production entrypoint; canonical semantic proposals, four inline case bundles, positive/negative compatibility and saved-only delivery receipts. Original public-highway review and single exclusive bidirectional center-turn-lane designation remain prerequisites for physical acquisition. Keep the assignment partial until strict delivery readiness passes.

## 2026-11-23 source-gated Native scene checkpoint

`native_scene.py` now checks the retained map and highway review source hashes and live OpenDRIVE before spawning the exact case. It requires a source-hashed spawn plan with two distinct vehicle actors, four exact RGB sensors at the pinned profile and 20 Hz synchronous world settings. Failed vehicle/camera spawn destroys prior actors. `run_scene_capture` joins the spawned scene to the existing Native 900-frame default runner and releases all actors and listeners on success or failure. The diagnostic integration test uses four frames and tiny synthetic camera images; it proves the source-to-capture software path, not physical lane design, receiving traffic or merge distance.

Pinned preflight, 51 focused CPU tests and scoped static check pass in `cpu-spawned-scene-*.log`; the exact scoped strict gate exits 1 on truthful partial. Commands and SHA256 receipts are in `result.json`. Remaining CPU work: reviewed production site and spawn plan, owned world snapshot/restore, exact semantic proposals and case bundles, positive/negative runtime compatibility and saved-only delivery receipts. Actual physical 50-foot measurement and legal interpretation remain unverified.

## 2026-11-24 Native scene cleanup after sensor failure

`NativeScene.close` now tries to stop every camera and destroy every spawned vehicle and sensor even when a sensor stop or actor destruction fails, then reports the first cleanup error. Partial-spawn cleanup likewise preserves the original spawn failure while attempting release of every actor already created. Two new CPU tests force sensor-stop failures at normal close and during a failed camera spawn; all spawned actors are destroyed in both paths. This is a Native resource lifecycle invariant, not an original physical or legal observation.

The full assignment suite passes 53 tests (`cpu-scene-cleanup-tests.log`). Pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Four SHA-bound logs are in `result.json`. Next CPU work remains reviewed original highway and exclusive bidirectional center-turn lane source, owned world snapshot/restore, canonical semantic proposals and case bundles, compatibility, saved-only processing and delivery receipts. Actual 50-foot travel measurement and vehicle reference convention remain unverified.
