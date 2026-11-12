# heldout__C126064__LVMC-11-12-020__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 authorized marker and original-course continuation

`case-plan.json` now specifies two exact turns, one targeting the indicated
course and one targeting a divergent path, in a comparison that holds the
physical markers, median-opening intersection, vehicle and capture plan fixed.
`marked_course_measurement.py` requires separate source references for municipal
jurisdiction, the intersecting-road geometry and marker authorization; it
rejects markers outside the sourced intersection. It joins every original body
footprint to the frame map and reports centroid/corner distances to the
indicated polyline throughout the turn. No numeric legal disobedience cutoff is
invented.

Two CPU tests pass, including out-of-intersection marker and wrong actor
rejection. Run `.venv-cpu/bin/python -m unittest discover -s
work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`21a8336d6a48f9beff492c4bc9911b0d37a6f2a5c9a4e4626ee959705694cede`.
Scoped complete passes; strict rejects the truthful partial status. Next,
construct a sourced Native median-opening intersection with physical authorized
markers, four-camera capture and the first exact saved finalizer, then run
offline, positive/negative compatibility and saved processing. Physical marker
presence, authorization and any legal outcome are unverified.

## Frozen scope and source

- Law: LVMC 11.12.020 — When authorized markers, buttons, or other indications are placed within an intersection indicating the course to be traveled by vehicles turning thereat, no driver of a vehicle shall disobey the direction of such indications.
- Cell/actor: C126064 / motor_vehicle_driver; layout `median_opening`, maneuver `turn`, control `turn_path_marking`.
- Exact input: `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/assignment.json` (SHA256 `99c4b9c957c0c22c44d5626cbb0c525f30d07157c63e93d8a7509f2172127b83`).
- Witness: `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: dev.regulatory_sign, st.lane_marking, dev.governs, st.intersection, drv.turning, kin.path_length, rel.occupies.

## Required source and construction review

1. A realizable intersection incorporating the median opening, rather than an isolated opening assumed to be an intersection.
2. Any additional signal configuration and its governance.
3. Applicable LVMC jurisdiction.
4. Construct an intersecting-road configuration incorporating the median opening and document its intersection boundaries.
5. Document any additional signal configuration and governance.
6. Establish applicable municipal jurisdiction and driver control.
7. Establish indication authorization, placement within that intersection, indicated course and relationship to the selected turn and median opening.
8. Preserve unresolved definition incorporation and the absence of a numerical disobedience criterion.
9. The authorized marking's course and relationship to ego's turning route and median opening.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-12 source-hashed Native marker construction checkpoint

`marked_course_native.py` implements CARLA-lazy physical turn-course marker placement from a SHA-256-bound authority record: it requires intersection/median-opening identity, checks that each marker maps to a Native junction, creates each configured marker blueprint, reads back actual x/y placement within 0.05 m and destroys partially spawned markers on failure. Four CPU tests now pass (`cpu-tests.log` SHA-256 `21e5b4282a47f75c7f16c5359a8cb27311fa6e2179003b6588f1f7a79877626b`), including source-tamper, non-junction and readback-mismatch rejection. The authority document in the fake test is a fixture claim, not real municipal authorization. The exact runner must supply a reviewed source file and site/map match, connect the indicated and divergent turn routes to this placement, retain four cameras and original bodies, then run exact offline/compatibility/saved and independent audits. Status remains partial; no physical or legal acceptance is claimed.

## 2026-11-12 compared Native turn-target checkpoint

`marked_course_native.turn_targets` now reads the same SHA-256-bound source record and selects either `indicated_course` or `divergent_course` targets. It requires a sourced intersection polygon and median opening with intersecting road, finite distinct route points, common approach and exit, a route through the sourced intersection, and Native junction waypoint lookup for interior turn targets. It rejects an identical divergent target and explicitly reports `actual_turn_observed: false`; eventual original body footprints remain the motion evidence. The source record still needs independent authority review and a site/map match before any real Native run.

Five package CPU tests pass: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`; current `cpu-tests.log` SHA-256 is `0150a2dfdd4d5c614240335d1de18f15b153072a82f702ae10b3ef32013ce8c6`. These include source tampering, non-junction route rejection and compared-turn fixed-endpoint construction. Status remains **partial**. Continue by connecting these targets to the ego controller and four named camera sources, then original-body finalization and exact primary offline/positive-negative compatibility/saved proof. The remaining second exact case, six fallbacks, semantic proposals and independent audits are worker-owned CPU work.

The same module now includes `control_step`, bounded speed and steering feedback for the selected turn targets, with a CPU test for straight versus turning steering and invalid engineering speed. Six tests pass; current `cpu-tests.log` SHA-256 is `ecea9e4e6a5bf90f8d8510c0c9bf9abe898efb186ea35300551600714784fc1c`. This controller is not yet connected to an ego actor or original capture and does not establish realized turn motion.

`FourCameraCapture` now creates `overview`, `approach`, `reference_corner` and `driver_reference` Native RGB sensors at 20 Hz, hands every original image to a caller supplied source recorder, rejects duplicate/wrong-size frames, waits for synchronized frame IDs, verifies the complete frame set and stops/destroys sensors. A fake Native lifecycle/join test passes; seven tests total pass with `cpu-tests.log` SHA-256 `11ffececa7a650c490ff5ea625a6c88df0f179a520a98fa56015ff18eea0f946`. The actual source-image encoder and ego runner integration remain CPU work, and the test images are not physical footage.

`marked_course_measurement.py` now exposes a saved-only CLI (`--source-dir`, `--case-id`, `--output`) that writes measurements only from retained marker, original body and frame-map sources. A subprocess test proves successful replay and rejection after deleting an original body source. Eight tests pass; `cpu-tests.log` SHA-256 is `76b3a3a24f9a94bc4ccf55a8abd4dd6d57ee720915eb064e13b61677428726b0`. The pinned runtime compatibility/saved receipt has not yet been run for an exact selected construction, so status remains partial.

`drive_turn` now applies bounded feedback to each source-selected target in a synchronous 20 Hz Native world, waits for the four camera frame IDs, records the ego actor ID, original time and four XY footprint corners extracted from eight Native bounding-box vertices, and brakes after the final target or a tick-budget miss. A fake Native test exercises the controller, frame/body recording and brake path. Nine package tests pass; `cpu-tests.log` SHA-256 is `9f8e643feeaa6d67da1fcfe745d9df4a245bb31463ff50a7c7ab3d0668630530`. The full runner must still assemble a reviewed site/authority source, actual vehicle spawn, source-image encoding and saved-processing proof. Status remains partial.

### 2026-11-12 original camera recorder and turn orchestration

`turn_source_recorder.py` now retains four named 20 Hz original BGRA camera streams as lossless FFV1 MKV sources and writes per-camera Native frame maps plus the original ego body-footprint stream. It rejects changed dimensions, truncated pixel packets, nonmonotonic frames and incomplete camera/body joins. `marked_course_native.execute_marked_turn` now joins SHA-bound physical marker placement, the source-selected turn target, camera callbacks, the original recorder and body samples, then closes cameras/recorder and destroys owned markers even after a turn failure. The caller still must provide a reviewed site/authority source and an owned ego.

Fourteen CPU tests pass, including full FFprobe decode counts for all four small original streams and failure cleanup. Command: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 `44c3bcb37fcd601f54e046f366c9c10eb563f743bc31dce7966c0555e88194ff`. The source videos from these tests were temporary diagnostics and are not returned recordings. Exact construction manifests, case-specific finalizer integration, three fallback constructions per selected case, saved-processing and independent audits are still CPU work; status remains **partial**.

### 2026-11-12 batch strict outcome

After the updated 14-test CPU source-recorder proof, `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete` exited 0. The full strict batch command `timeout 300s .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` because 16 results, including this one, remain partial. This is unfinished worker CPU preparation, not an external runtime dependency.

The source recorder now writes exactly the three retained raw inputs consumed by `marked_course_measurement.py`: `marked_intersection.json`, `turn_body.jsonl` and `video_frames.jsonl`. `record_scene` binds the caller-supplied source hash and requires separate jurisdiction, intersection and authorization citations; the original physical marker readback is retained, while `authorization_verified_by_worker` remains false. `seal()` rejects missing scene context and camera/body timestamp drift, and a CPU fixture runs the saved-only measurement directly on the recorder's outputs. The fixture citations are explicitly synthetic. Fifteen tests pass; `cpu-tests.log` SHA-256 `24009a9ddc733ff645e44057a7b6a8a0eb865048b15adb326cd5f785f905975e`. This demonstrates software source compatibility, not municipal authorization or an actual Native turn.
