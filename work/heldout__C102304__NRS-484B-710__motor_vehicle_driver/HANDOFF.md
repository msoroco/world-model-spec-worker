# heldout__C102304__NRS-484B-710__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-710, cell: C102304, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/assignment.json` (65306863f6f9c06d3529c3d84d4f9aa701426fcc3ee6e2c896ea225ff19f9966).

Exact law text: The driver of any motor vehicle other than an authorized emergency vehicle on official business shall not follow any fire apparatus traveling in response to a fire alarm closer than 500 feet or driving to or park such vehicle within 500 feet of fire apparatus which stopped in answer to a fire alarm.

Accepted recording summaries to review: 2; inventory `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/evidence.json` (5466012de98df865a29f340b00bd7381e260caea973095f5b84a308e2752699a). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and bound comparisons, complete portable runner/construction, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery audit remain to implement. Standalone source-recomputing comparison audit, traveling and stopped-apparatus feedback controllers, and a retained original-tick source writer are implemented but have not yet been bound to an exact case runner.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C102304__NRS-484B-710__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Existing evidence and exact gaps

The accepted 450/550 ft commanded following pair is source-bound in `case-plan.json.evidence_review`; it is limited to a traveling apparatus. Its reference check explicitly excludes the stopped branch. Commanded gaps are not substituted for the measured full-footprint gap. Alarm purpose and ordinary-subject status are synthetic premises.

Pending NRS 484B.710 alternatives: at-500 ft following boundary; driving to a stopped apparatus below/at/above 500 ft; parking within 500 ft of a stopped apparatus; and the authorized-emergency-vehicle-on-official-business exception. Build exact comparisons and four-camera saved-processing proofs before strict readiness.

## Full-text branch inventory (planning, unimplemented)

- traveling fire apparatus: follow at below/at/above 500 ft using measured footprint separation
- stopped fire apparatus: drive to within/at/outside 500 ft
- stopped fire apparatus: park within/at/outside 500 ft
- authorized emergency vehicle on official business exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## Current CPU construction checkpoint

`fire_distance.py` measures the minimum distance between complete ordered Native ground-footprint polygons and separately records centre distance. It reads retained Native JSONL, binds the SHA256 of the original bytes, and rejects missing/invalid geometry, missing ticks, changed actor identities and missing source. `fire_branch.py` joins that measurement to retained frame/time-matched participant-state JSONL and reports active frames for traveling/following, stopped/driving-to, and stopped/parked alternatives. Traveling following uses footprint separation; stopped-apparatus alternatives use centre distance, per the assignment's distinct `rel.surface_gap` and `rel.centre_distance` observation terms. Driving-to requires measured closing centre distance across consecutive frames; merely moving near a stationary apparatus is rejected. It preserves alarm-purpose and authorized/official-business context as separately sourced premises, and reports below/at/above 500 ft samples with a 1e-6 ft floating-point reporting bin that has no legal meaning. Neither module gives a legal verdict. `fire_comparison_audit.py` independently checks a declared fixed/difference comparison, source hashes, 500 ft bin membership and the measurement recomputed from retained sources. It rejects stale hashes, missing sources, changed fixed conditions and a rehashed but altered measurement. Its CLI takes a JSON comparison specification and emits a JSON receipt; exact case specifications are pending construction. `follow_controller.py` adds a CARLA-lazy traveling-case feedback controller targeting an engineering 500 ft projected longitudinal body gap. It validates aligned following geometry, measures both approach directions, bounds throttle/brake and rejects invalid/reversing configurations. It does not establish an actual full-footprint 500 ft gap; `fire_distance.py` must measure that from retained Native frames after capture. `tests/test_fire_distance.py`, `tests/test_fire_branch.py`, `tests/test_fire_comparison_audit.py`, and `tests/test_follow_controller.py` cover these paths. Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v`; `cpu-tests.log` exit 0, 23 tests, SHA256 26aba19a627bedf7ff7aa1e7d52e36a704afd8f51cbc667c007a916113255466. This is implemented measurement, comparison and one controller component, not an exact-case finalizer or compatibility receipt.

Next CPU action: construct the at-500 ft traveling case and stopped apparatus driving/parking below/at/above cases, bind retained Native footprint and participant-state JSONL acquisition plus `fire_branch.py` to the saved finalizer, and test the first exact case through offline, positive/negative compatibility and saved processing. Preserve accepted 450/550 ft traveling evidence without replay. Then complete branch comparisons, exception case, three tested fallbacks per case, proposals and independent audits before the assignment strict gate.

## Current gates

`.venv-cpu/bin/python runtime.py preflight` passed with pinned Python and Lean 4.28.0; repository unit tests passed (6 tests). Assignment `worker_check.py --complete` passed static checks (`worker-check.log`). Assignment `--complete --require-delivery-ready` failed as expected with `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`). Batch strict gate has the same failure in `work/_shared/batch-strict-gate.log`; 49 of 51 assignments are still partial. These are unfinished CPU deliverables, not an external dependency.

The current checkpoint has 23 passing assignment tests. The updated environment passes `.venv-cpu/bin/python runtime.py preflight` (see `work/_shared/preflight.log`), and repository tests pass (`work/_shared/repository-tests.log`). The complete batch checkpoint gate passes (`work/_shared/batch-checkpoint-gate.log`). The complete batch strict gate was rerun and fails with `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/batch-strict-gate.log`); 49 of 51 assignments remain partial. The next CPU construction and proof action is recorded below; the assignment remains partial until its strict gate passes.

## Current construction and source checkpoint

`stopped_controller.py` commands a stationary-apparatus approach to a selected centre distance (450/500/550 ft engineering targets) or a parked hold. It checks ahead-of-ego same-lane geometry, refuses a moving apparatus and reverse motion, and applies bounded brake/throttle plus hand brake only after speed and position criteria. `tests/test_stopped_controller.py` exercises both approach directions, all three target distances, park transition and invalid geometry. These commanded distances do not prove the realized statutory boundary.

`fire_source_capture.py` writes original-frame `participant_footprints.jsonl` and `participant_state.jsonl` with stable actor IDs, eight-vertex world-box-derived ground corners, motion/following/parking state and explicit lamp/siren readback inputs. `tests/test_fire_source_capture.py` sends those retained raw files through `fire_branch.measure_branch` for both directions and verifies rejection of missing readback and skipped frames. The runner must still supply physical lamp/siren readbacks, call the writer on each synchronized Native tick, retain both files in the attempt and bind them to saved processing. Alarm purpose and emergency-vehicle authorization require separate sourced context; warning devices alone cannot establish them.

Current proof command: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` exits 0 with 23 tests; log `cpu-tests.log`, SHA256 26aba19a627bedf7ff7aa1e7d52e36a704afd8f51cbc667c007a916113255466. `.venv-cpu/bin/python runtime.py preflight` exits 0 (log `work/_shared/preflight.log`, SHA256 7df4d1fbce17583da343c118d91186e5dcb91e5ebb342ef1adbb809ff6edbf90). Repository tests exit 0 (log `work/_shared/repository-tests.log`, SHA256 f7984587660d832b9fef9e08b5c41c6f6ed674bb151622f963d5a43af9af53db).

Next CPU action: bind the first at-500 traveling case to a portable runner, four named cameras, this raw source writer, exact finalizer and a positive/negative diagnostic. Run offline and compatibility for that exact construction, then saved processing. After that expand the stopped drive-to, parking and exception comparisons, candidate constructions and independent audits. Assignment remains partial; CPU preparation is still required.

## Current gate receipts and exact continuation

- assignment checkpoint: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/worker-check.log`; exit 0; SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- assignment strict: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/strict-gate.log`; exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
- batch checkpoint: `work/_shared/batch-checkpoint-gate.log`; exit 0; SHA256 b240d7e9206f7ce14c8a3993e3129987c0a88e4abdbae1a23fc38114833693b5.
- batch strict: `work/_shared/batch-strict-gate.log`; exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
- fixture materialization: `work/_shared/fixture-materialize.log`; exit 0; SHA256 ca45af1fbe25db91750e641d349c9e5fa370e374a7ede065bf4f4eb95c26b006.
- optional selftest: `work/_shared/runtime-selftest.log`; exit 1; SHA256 6a0df4c3a3502b20237c513e0e2a06084b4031e6bf2a434fbd9330fb12ff0858.

The optional `runtime.py selftest --output .runtime-work/current-selftest` exited 1 because its optional smoke fixture was not exported; its own error instructs exact-case compatibility. This is not an external dependency or readiness proof. `runtime.py fixture --recipe runtime/fixtures/example-recipe.json --output .runtime-work/current-example` exited 0 and verified textual fixture materialization with the installed media tools, but is not a case-specific compatibility receipt. The assignment and batch strict gates both reject partial packages at `preparation.py:276`.

Resume by binding `fire_source_capture.py` to the first exact runner and retaining its two JSONL sources, implementing a saved finalizer and four-camera plan, then running `runtime.py offline` and positive/negative `runtime.py compatibility` for that exact case. Continue with saved processing and the remaining statutory branches and audits; do not mark ready before assignment strict gate passes.

## Saved fire finalizer checkpoint (current)

`fire_finalizer.py` now reads original `video_frames.jsonl`, `trace.jsonl`, `participant_footprints.jsonl`, `participant_state.jsonl`, and `fire_context.json`. It checks contiguous source identities and frame/time joins, invokes `fire_branch.measure_branch`, hashes every consumed source, and emits a case-specific analysis report and conservative Native-shaped result. Alarm purpose and emergency authorization remain separately sourced premises; warning lamps and siren do not prove them. The result leaves setup and physical completion unconfirmed. Positive CLI and missing-original-state negative tests, plus 27 previous tests, pass via `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v`; `cpu-tests.log` exit 0, 29 tests, SHA256 bbc30f2ad675b52d09f4f035b1b01beaa2ed510245b330044bd10cadb931139e.

Next bind the at-500 traveling case to a runner that retains all five source files and the four named camera streams, then run `runtime.py offline`, `runtime.py compatibility`, and `runtime.py process-saved` for the exact case. Complete the stopped drive-to, parking, exception comparisons, three distinct fallback constructions per selected case, canonical proposals, and independent delivery audit. This is unfinished worker-owned CPU work, not an external blocker. No new case or compatibility proof is claimed by this checkpoint.

## Exact case and comparison construction queue

`case-plan.json` now lists ten qualified planned cases: traveling follow at commanded 499/500/501 ft, stopped drive-to at 450/500/550 ft, stopped park at 450/500/550 ft, and authorized-emergency follow at 500 ft. Four comparisons hold route, alarm premise, camera/duration policy, and branch-specific controller policy fixed while changing target distance or the sourced exception context. These are planned probes, not new recordings or passing constructions. The accepted traveling 450/550 ft recordings remain separate source-backed evidence; they are not replayed or counted as new exact cases. Each planned case records a specific physical risk and a measured-source trigger. The emergency-vehicle comparison must verify blueprint and body geometry equivalence rather than assume it.

The first runnable case remains `heldout__C102304__NRS-484B-710__motor_vehicle_driver__traveling_follow_500ft`. Bind `fire_finalizer.py` and the original-tick source writer to a CARLA-lazy runner and the four camera streams, then run exact offline and positive/negative compatibility and saved processing. Finish the remaining cases and three fallback constructions per case before strict readiness.

## Current return checks

- assignment checkpoint: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/worker-check.log`; exit 0; SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- assignment strict: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/strict-gate.log`; exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
- batch strict: `work/_shared/batch-strict-gate.log`; exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.

The strict failure remains `Preparation acceptance failed: partial/missing packages remain` at `runtime/scenario_pipeline/worker_exchange/preparation.py:276`. This is expected for the 49 partial packages and does not certify the newly planned cases. The next CPU action is the first exact runner and source-bound offline/compatibility/saved-processing proof described above.

## Original-tick capture integration checkpoint

`fire_capture_session.py` now joins a caller-owned `PipelineCapture.capture` call, `FireSourceRecorder.append`, and `native_output.FrameMap.append` on the same original tick, with an exclusive sourced `fire_context.json`. The runner must still create the caller-owned PipelineCapture and all four actual RGB camera streams. `tests/test_fire_capture_session.py` exercises the joined files through `fire_finalizer.analyze` in both approach directions and rejects an absent lamp readback before writing trace data. The full assignment command `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` exits 0 with 31 tests; `cpu-tests.log` SHA256 718c51188f48fac8fe3aa7dbe35b6e5d6dc81296e2fa8ab0ff01be1d0b669ed3. No actual Native tick or camera frame was produced by these CPU tests.

## Latest gate receipts after capture integration

- assignment checkpoint: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/worker-check.log` exit 0, SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- assignment strict: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/strict-gate.log` exit 1, SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
- batch strict: `work/_shared/batch-strict-gate.log` exit 1, SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.

The strict failure still states `Preparation acceptance failed: partial/missing packages remain`. C102304 remains partial because the selected exact case and candidates have no executable construction or full offline/compatibility/saved-processing proof. Resume with the at-500 traveling runner and four named camera streams, bind the current source/finalizer modules, then expand the remaining exact cases and independent audits.

The saved result now gives each retained acquisition entry the Native recording-evidence `name`, `unit`, and `reference` fields plus its SHA256. After this correction, the 31-test suite remains passing; current `cpu-tests.log` SHA256 755eda220c06cc1f0a2ac4a78a65b4d95f9254d2849997471a9473b83622d74e. This is still a partial source/analysis integration and not an exact-case compatibility receipt.

## Final checks for this checkpoint

- `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/worker-check.log` (assignment checkpoint) exit 0; SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- `work/_shared/batch-strict-gate.log` (batch strict) exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.

The updated analysis code and result claim are covered by 31 passing CPU tests. The complete batch still has 49 partial assignments and 2 ready assignments; `--require-delivery-ready` fails as it should. Continue worker-owned construction and proof work from the first at-500 traveling exact case.

## Current four-camera construction checkpoint

`fire_camera_capture.py` creates `overview`, `approach`, `reference_corner`, and `driver_reference` RGB sensors attached to the subject at 20 Hz using the prospective 1920x1080 + three 1280x720 profile. It rejects missing sinks, changed dimensions, duplicate frames and a missing original-frame join. `FFmpegSourceSink` writes original BGRA bytes as lossless FFV1 `.mkv` sources and checks encoder exit. `tests/test_fire_camera_capture.py` fake-world tests exercise sensor creation, frame joins, rejection and encoding command/byte checks. The real FFmpeg/ffprobe smoke at `.runtime-work/fire-camera-smoke/approach.mkv` reports FFV1 1280x720; this is generated diagnostic media, not a recording or visibility proof. Camera placement is provisional and actual participant visibility remains a physical risk.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` passes 34 tests; `cpu-tests.log` SHA256 e5e47797fe017520afb4034a6f46666d27d5d0a5686c1caac47030db5f3ea391.

Next CPU construction: implement the first traveling-follow 500 ft CARLA-lazy runner, create the four sinks and `PipelineCapture`, call `FireCaptureSession.capture` once per original tick with actual warning-lamp and siren readbacks, and close/verify all camera streams before saved processing. Then bind `fire_finalizer.py` and run exact offline, positive/negative compatibility and process-saved proofs. Expand the remaining cases, fallbacks, proposals and independent audits before readiness. The current sink and fake-world tests are components, not an exact-case receipt.

- assignment checkpoint: `worker-check.log` exit 0, SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- assignment strict: `strict-gate.log` exit 1, SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
The strict assignment gate still rejects the partial package at `preparation.py:276`; it does not certify readiness.

Batch return gate after this change: `.venv-cpu/bin/python worker_check.py --complete` exits 0, `work/_shared/batch-checkpoint-gate.log` SHA256 b240d7e9206f7ce14c8a3993e3129987c0a88e4abdbae1a23fc38114833693b5. `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 at `preparation.py:276` because partial packages remain; `work/_shared/batch-strict-gate.log` SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292. No assignment status was promoted.

## Current Native construction integration

`fire_route.py` now samples a single continuous Native lane and requires measured uphill and downhill waypoint grades with the crest between the selected actors; it rejects flat/discontinuous routes and tests both approach directions. This is a map-shape construction check, not a measured sight line. `runner.py` is the CARLA-lazy Native entrypoint for the planned traveling-follow 500 ft case. It selects that route, spawns an ordinary ego and fire apparatus, applies lane-following and spacing controls, joins each original tick to `PipelineCapture`, `FireCaptureSession` and all four camera frames, closes the source encoders and seals the capture only after world settings restoration. `fire_camera_capture.py` now waits for all four camera callbacks for each frame and rejects callback errors/timeouts. When the Native actor exposes no siren getter, `participant_state.jsonl` records an explicit unknown; it does not infer alarm purpose from warning devices.

The assignment test command `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` passes 41 CPU tests; `cpu-tests.log` SHA256 d9b04968e878282fc071c09b2d7ba73a570c251fc243ab805bdd30479dd93124. The assignment checkpoint gate exits 0, while the strict gate still exits 1 because status is partial. The new runner has no exact construction/config bundle or compatibility and saved-processing receipt and has not run against CARLA. The next CPU action is to bundle the first case in `execution-manifest.json`, supply its case-specific diagnostic sources and measurement contract, run `runtime.py offline`, positive/negative `runtime.py compatibility`, and `runtime.py process-saved`; then expand the other nine cases, fallbacks, proposals and audits. A local Native run later must confirm a usable crest, device readbacks, motion and camera visibility.

## Independent saved-source audit checkpoint

`delivery_audit.py` independently rereads and hashes the six retained source files, recomputes the fire measurement with the selected finalizer, verifies original frame identities and fully decodes all four named camera sources through the shared media auditor. Its CPU tests reject changed original state, missing original state, missing camera and a short decode. The tests use a decoder stub and textual source fixtures; no physical visibility or real video acceptance is claimed. `runner.py --check` now validates a materialized `config.json` when present and rejects a wrong exact-case identity.

Current test command `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v` exits 0 with 45 tests; log `cpu-tests.log` SHA256 025aa275b2163216bbba094c9570523018e2bfb2c844111a360a4a5bcc4224d5. Next bundle the first exact case, run its source-bound full compatibility and saved-processing path, then expand the remaining cases, three fallback constructions each, semantic proposals, and audit/queue bindings. The assignment remains partial.

## Final gate receipts for this checkpoint

- assignment checkpoint: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/worker-check.log` exit 0; SHA256 e1c2de7288b0b7a530f361a3a1db8c5cf337461cf87d1b7203971fd4657a2645.
- assignment strict: `work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/strict-gate.log` exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.
- batch strict: `work/_shared/batch-strict-gate.log` exit 1; SHA256 89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292.

The strict gates still reject partial packages at `runtime/scenario_pipeline/worker_exchange/preparation.py:276`. C102304 has executable CPU components but lacks the required exact-case proof bundle, and 48 other assignments also remain partial. This is unfinished CPU preparation, not an external blocker.
