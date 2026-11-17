# Handoff: heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver

## Frozen scope

Whenever an illuminated flashing red or yellow signal is used in conjunction with an official traffic-control device, it shall require obedience by vehicular traffic as follows: When a yellow lens is illuminated with rapid intermittent flashes, drivers of vehicles may proceed past such signal and through the intersection or other hazardous location only with caution.

Cell C24753: blind_intersection / travel / flashing_yellow_signal; actor heavy_vehicle_driver.

## Full-text branch inventory for CPU construction

- Rapid intermittently flashing yellow lens used with official traffic-control device at intersection or hazardous location.
- Proceeding past signal is allowed only with caution; compare concrete observable approaches while leaving legal caution judgment unresolved.
- Check yellow lens and official conjunction; do not apply flashing-red branch from another subsection.

## Current checkpoint

Four planned cases compare a heavy vehicle from east/west approaches, engineering approach speed and crossing-traffic presence while retaining the same official flashing-yellow premise. `flashing_yellow_heavy.py` requests a physical yellow signal head, linked official device, blind intersection, heavy subject and optional crossing vehicle through an adapter. Its source-shaped measurement requires original 20 Hz signal and participant readbacks and keeps the legal “with caution” judgment open. Tests cover both approach directions, creation calls, missing-source rejection and fixed-condition comparison; `cpu-tests.log` SHA256 is `af7e3f206e5267a8ff2e06d0a2fefd00e69a646799c2c61bbcd2fecaea8941d3`.

Status remains partial. A concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C24753__NRS-484B-310-2__heavy_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## 2026-11-17 concrete Native signal and heavy-vehicle adapter checkpoint

Restored `flashing_yellow_heavy.py` and its test file from the exact-byte archives already retained in `result.json`. The source now contains CARLA-lazy `discover_native_control`, `construct_native`, and `NativeYellowController`. The helper selects separate east/west signal heads with OpenDRIVE IDs and affected-lane waypoints at one junction, derives the governed heavy route and a perpendicular crossing route from original map waypoints, spawns explicitly chosen heavy and crossing blueprints, destroys an owned actor on failed construction, commands and reads back the yellow/off signal state per tick, and verifies restoration of its initial state. Official status remains a cited premise, not inferred from the simulated traffic light. No CARLA run or legal caution judgment is claimed.

The returned fake-world test exercises both directions, all four planned cases, heavy/crossing actor creation, missing official-control premise, failed crossing spawn cleanup, yellow/off readback and light restoration. Four package tests pass in `cpu-tests.log` SHA-256 `49562b4da647cd8f2933d1d524589c471e7ff7f8126065f2e04e1d199a4a7bbf`; current source SHA-256 `8b34ca8e548fb2a0cbf7934e2e777e4049495e51f5397b0e751c889050bdd68e`. Pinned CPU preflight and scoped nonstrict `worker_check.py --complete` pass. Scoped strict still exits 1 at `preparation.py:276` because this result remains partial.

Next worker CPU action: build one exact selected case around this Native helper with the four named raw camera streams, frame-joined signal/device/vehicle source readback, finalizer and source-bound positive/missing-source compatibility; then run `process-saved` before expanding the other selected cases and three fallbacks each. Independent comparisons, physical preparation, semantic proposal and delivery audit remain to construct.

To remain within the 10,200-file return cap, exact bytes of three no-longer-live helper scripts were added to `work/_shared/historical-receipts-bundle-20261116.json` and their owner scoped strict gates passed after removal: C111706 `validate_semantic.py`, C230627 `validate_semantic.py`, and C102304 `validate_delivery_bindings.py`. Two other trial removals failed their owner scoped strict gate and were restored byte-identically before this checkpoint. The returned tree is 10,200 files with none above 2 MiB. No frozen input, runtime, batch, or Git operation changed.

## 2026-11-17 post-tick original source collector checkpoint

Extended `flashing_yellow_heavy.py` with `NativeSampleCollector`. For a tick joined to all four camera frames, it reads the selected light's post-tick state, original heavy-vehicle transform and velocity, crossing-actor transform when present, and the world snapshot frame/time. It emits a canonical `video_frame` / `carla_frame` / `time_s` map and rejects a changed governed head, changed post-tick light state, skipped frame or non-20 Hz time. The official-control source is retained as an identified premise, with `official_device_status=premise_unverified`; `signal_head_visible` and the legal caution judgment remain unknown until actual camera/source review. This code does not run CARLA.

The fake-world test now exercises ten joined 20 Hz frames, canonical map identity, the unresolved official/visibility status, skipped-frame rejection and refusal by `measure` to accept an unverified visible yellow signal. The four-test package suite passes. Current script SHA-256 `6ea357c24b96cec7cf4edb8a84ce8c1b80ae6f194ce909fb5ce5cfb8735fedaa`; test SHA-256 `04f8e0baf9cda44aaab2c6e2e4bc3621f210d5ade8170b2696a1c2970bf64cd7`; `cpu-tests.log` SHA-256 `49562b4da647cd8f2933d1d524589c471e7ff7f8126065f2e04e1d199a4a7bbf`. Pinned CPU preflight and scoped nonstrict `worker_check.py --complete` pass; C24753 remains partial. The next CPU step is the four-source-camera acquisition and first exact case runner/finalizer with source-bound positive and missing-source compatibility before other cases and fallbacks.

## 2026-11-17 four original source cameras and frame barrier

`flashing_yellow_heavy.py` now carries four named RGB source camera plans (`overview`, `approach`, `reference_corner`, `driver_reference`) with 1920×1080 overview at 20 Hz and three detail views. `FFV1SourceSink` retains each original BGRA stream losslessly, checks exact source byte counts and encoder exit. `NativeSourceCameras` attaches all four sensors to the subject, rejects wrong dimensions and duplicate frames, waits until all four have the requested original frame, verifies the final exact frame inventory, and closes its owned sensors. `NativeSampleCollector.capture` now requires that four-camera barrier before emitting the joined signal/vehicle source row and canonical frame map. No actual CARLA capture or physical visibility is claimed.

The six-test fake CPU suite covers the four camera inventory, 20 Hz sensor configuration, full frame joins, duplicate rejection, callback-error propagation, missing-camera rejection, raw source byte count, FFV1 command and closed sink behavior. `cpu-tests.log` SHA-256 `f0e3303d341f5b114f24bfa71621c576e3861b6632b82a05927321e7c5093ef2`; script SHA-256 `2e9727378a70dc8cf24ae370849ece0cbb74af33f2c6c4e7f62a5fca2987abf0`; test SHA-256 `7378d1729d8259443c938c541565ac059a3da307bc878ab24370de4deb04d968`. Pinned CPU preflight and scoped nonstrict C24753 check pass. `result.json` remains partial and binds these hashes.

Next CPU action: build and prove the first exact `east_cautious_proxy` runner/config/construction using the camera and original-source helpers, implement its saved finalizer and retained diagnostic recipe, then run exact offline, positive/missing-source compatibility, and saved processing. The other selected cases, three fallbacks per case, semantic proposals, physical preparation and independent audits remain worker-owned. The returned tree is at the 10,200-file cap with no file above 2 MiB; free slots only by lossless archiving and owner scoped strict recheck.
