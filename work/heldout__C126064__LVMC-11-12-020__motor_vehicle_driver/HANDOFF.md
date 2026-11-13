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

### 2026-11-12 Native exact-variant runner wiring

`native_runner.py` now accepts only the two planned exact case IDs and a SHA-256-bound site/authority source. It checks the median-opening/intersecting-road source fields and exact Native map name, derives the common approach pose, imports CARLA only inside `run`, spawns an ego, starts four original camera encoders, calls `execute_marked_turn` with the indicated or divergent target, writes a Native result, and restores world settings and owned resources even when turn execution fails. It retains `authority_verified: false`; the CPU fixture's authority string is not accepted as municipal evidence. `tests/test_native_runner.py` proves both exact identities, source-tamper rejection, map mismatch rejection, argument wiring and failure cleanup with a fake Native client. All 17 assignment tests pass: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 `280bf8efca5f1347a2ca277b2f0d5e7c5a0fa1997f7399798281ccbfae73b04d`. Scoped nonstrict `worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete` exits 0.

Status remains **partial**. Next exact CPU work is to bind a reviewed site/map source to each exact construction, package the runner and finalizer with four camera and duration plans, run primary offline/positive-negative compatibility and saved processing, then expand three risk-triggered fallbacks per case and independent audits. Native motion, actual authorized placement, camera pixels and legal conformance are unverified. No CARLA command was run here.

### 2026-11-12 fixed original capture duration

`marked_course_native.drive_turn` now collects exactly 160 synchronized 20 Hz camera/body frames for either compared turn. After the sourced targets are reached, it applies the brake and continues recording original camera frames and body footprints through the fixed window. It rejects a turn that exceeds that window rather than silently producing a shorter or incomparable recording. The Native fixture exercises the full 160-frame body/time join and the overrun rejection. All 17 assignment CPU tests pass (`cpu-tests.log` SHA-256 `306075f01c2e9ab48d68240d639d263047b6ff3d3d345eadd79301c7d1c45b67`). The changed controller is work-owned source, not yet bound into an exact manifest; exact offline, compatibility and saved-processing receipts remain CPU work. This test does not establish actual Native turn motion or camera visibility.

The updated pinned CPU preflight passes. The complete strict batch gate rerun after the C111610 construction returned exit 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`. Its frozen file-count and preliminary checks passed. This assignment remains **partial**. Resume with the exact indicated-course construction, source-hashed synthetic diagnostic and saved-only finalizer; then build the divergent comparison and its three risk-triggered fallbacks per selected case. Do not use the fixture authority text as municipal authorization. The next scoped gate is `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready` after all CPU proof bindings exist.

### 2026-11-12 retained authority-source binding

`turn_source_recorder.py` now copies the exact SHA-256-checked site/authority
source into the original saved attempt as `authority_source_original.json` and
binds its digest in the source seal. `marked_course_measurement.py` requires that
original record, checks its digest against `marked_intersection.json`, and checks
that the cited jurisdiction, intersection, authorization, polygon, indicated
course and median-opening claims agree with the source. A saved attempt with a
missing, changed or scene-mismatched source now fails before turn measurements.
This is source provenance, not proof that the fixture claim is legally authorized.

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`
passes 18 tests; `cpu-tests.log` SHA-256 is
`3a13435d0bda28947bc091d1c0675d459781622a66b8f4266163ee81599eee62`.
The next exact construction is the indicated-course bundle with a synthetic,
explicitly unverified diagnostic site source, a source-bound Native finalizer,
and exact offline, positive/negative compatibility and saved-only proofs. Then
construct the divergent case, fallbacks, proposals and independent audits.
`result.json` remains partial; no physical or legal acceptance is claimed.

### 2026-11-12 first exact construction and offline proof

`build_indicated_bundle.py` packages `indicated-construction.json` and
`execution-manifest.json` for exact case
`heldout__C126064__LVMC-11-12-020__motor_vehicle_driver__indicated_course`.
The materialized entrypoint checks the exact identity, four named camera plan,
20 Hz and 160 frames, then requires `MARKED_TURN_SITE_SOURCE` and
`MARKED_TURN_SITE_SHA256` for a Native run. It never silently substitutes a
fixture authority claim. The construction embeds the tested Native marker,
route, source-recorder and measurement modules plus the 18 CPU source/geometry
tests. The primary exact offline command recorded in the manifest passed;
`indicated-offline.log` has SHA-256
`de2152cc4311a225c6e383a1f1f8a4b6ad8990effabb9231ed22c598e26ba66a`.
The scoped nonstrict gate is the next package check. This is a construction
proof, not source-bound compatibility, saved processing or municipal approval.

Next CPU action: connect the retained four original streams and authority/body
sources to a Native-shaped diagnostic recipe and finalizer, run exact positive
and missing-source compatibility followed by saved processing for this primary,
then construct the divergent case and three independently proved physical-risk
fallbacks per case. Implement semantic proposals and independent delivery and
comparison audits before the scoped strict gate. Keep `result.json` partial until
all these CPU proofs pass; original map geometry, authority, pixels, motion and
legal course conformance remain unresolved.

### 2026-11-12 linked divergent exact construction

The same `build_indicated_bundle.py` now packages the linked
`heldout__C126064__LVMC-11-12-020__motor_vehicle_driver__divergent_course`
in `divergent-construction.json`. It preserves the 20 Hz, 160-frame, four-camera
contract, ordinary driver/vehicle and explicit site-source requirement while
selecting the divergent target route from the same source. Its exact offline
materialization and all 18 embedded CPU tests pass; `divergent-offline.log`
SHA-256 is
`4e95378db036ba04aa9544349e11ce744bb2eeb9a6a90508f94a16d73cb286d4`.
Both exact primary constructions are in `execution-manifest.json`. These are
requested route constructions; no original Native turn path has been observed.

The scoped strict check still rejects the truthful partial status. Next CPU
work is the source-bound diagnostic/finalizer compatibility and saved proof for
each case, three risk-triggered fallback constructions per case, and independent
delivery/comparison audits. Then complete semantic proposals and the scoped
strict gate. Do not promote the package from these offline results alone.

The final scoped nonstrict command
`.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete`
passes after both constructions. The latest full batch strict command
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
finished with exit 1 at `preparation.py:276`, `Preparation acceptance failed:
partial/missing packages remain`. It passed the return-file cap. The package
status and reason remain truthful partial.

### 2026-11-12 independent marked-course comparison protocol

`comparison_audit.py` rereads both original site records, marker readbacks,
frame maps and body paths and reruns source-joined measurements. It rejects a
changed authority/site/marker, unequal capture count, identical body path or
missing measured course contrast. With 160-frame original attempts it also
requires all four named camera source files; full decode remains a separate
delivery-audit requirement. Its CPU selftest passes one source-shaped positive
and two negative probes (`comparison-audit-selftest.log`, SHA-256
`485bfbffe2cd7f311c29146d54be61c6ad976f1d1d404d0d74b3a06823d38e84`;
script SHA-256
`66142f8b9f5b090d4b2f1d1b23811b6c7fd2b793256e52032f1b89a8afff7e47`).
The case plan names the auditor; no original Native comparison or legal
conformance is claimed. The scoped nonstrict gate passes after this addition.

Resume with `.venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/comparison_audit.py --selftest`, then develop the
case-specific Native-shaped diagnostic and finalizer. The exact ready gate
still requires positive/missing-source compatibility, saved processing,
fallbacks, semantic stages, physical/delivery audits and an independent final
review of the original law and site source.

The final full batch strict rerun after this audit exited 1 at
`preparation.py:276` with `Preparation acceptance failed: partial/missing
packages remain`; its return-file cap passed. The 51 frozen assignments remain
35 ready and 16 partial. This case is still partial for the CPU work above.

### 2026-11-12 source-bound finalizer and first complete saved proof

`marked_course_finalizer.py` now measures the exact original authority/scene hash, physical marker positions, frame-joined full-body course and four named original camera sources. It emits `original_marked_turn_course.jsonl` and a Native result that leaves municipal authorization, visible marker pixels, maneuver completion and legal conformance unconfirmed. `turn_source_recorder.py` now writes `trace.jsonl` from the same retained original body samples at capture; the finalizer rejects a changed body/trace/frame join. The two exact construction bundles embed the finalizer and recorder. Current construction SHA-256 values are `4a6d113e2a811edd994221bf142befce041a6fb8c4b73f3a147f76e9e9861096` for `heldout__C126064__LVMC-11-12-020__motor_vehicle_driver__indicated_course` and `0da6fcb26384ce1751f1954752cc65e880d4701602facf8e089068835f67f498` for `heldout__C126064__LVMC-11-12-020__motor_vehicle_driver__divergent_course`.

`build_marked_diagnostic.py` builds the first exact textual fixture from a turn-shaped nine-frame synthetic source and adds original-shaped marker, authority and body files. Its authority claim is explicitly unverified and is not evidence that a municipal indication exists. The diagnostic SHA-256 is `6dc187cf10512c8c716ec93cab15c1f3b1feceb884e455ca9fe6ed944652ba0d`. `prove_indicated_primary.py` passes exact offline, positive compatibility, the negative removal of `authority_source_original.json`, and saved-only processing from a separately materialized attempt with originals preserved. The current compatibility receipt `indicated-compatibility-receipt.json` SHA-256 is `818f01f47830a8a29f7c25961b78468047048516e82db00ad9bd27d806a29c5a`; saved receipt `indicated-saved-receipt.json` SHA-256 is `dfe999c15d4904e6aa12e7c1a396412b7ed649fafd77efbec901e15c0cc1cd0c`. Both exact offline constructions passed after finalizer changes, and 20 CPU tests passed (`cpu-tests.log` SHA-256 `f795bfc334a25ad0dc5071344c26973bc0b84874c858a228c7739b08dff1ebe4`). The nonstrict scoped gate passes. `execution-manifest.json` binds the exact commands and current hashes.

Status remains **partial**. Next, build the divergent-course diagnostic from the same authority and marker source with its own original body path, then run exact positive/negative compatibility and saved processing. Construct and prove three distinct risk-triggered fallbacks per exact case; add independent physical and delivery audits; finish canonical semantic stages and source-observation mapping; review the original law and municipal authorization independently before the scoped strict gate. The case's current proposal is a partial compatibility input, not a complete semantic stage chain. Run `.venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/prove_indicated_primary.py` after any source or finalizer change, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready` only after every CPU deliverable is bound. No actual Native turn, marker pixel or legal finding is claimed.

### 2026-11-12 two-case delivery proof and original-law continuation

The same source-hashed, explicitly unverified authority and marker scene now drives both textual exact diagnostics. `divergent-diagnostic.json` changes the last three original body/trace/evidence positions consistently while keeping the authority bytes and marker positions fixed; its SHA-256 is `bdbd0b94970c41a3d48931c28633779cee31f1eb86c5ef3bbee9c8fe2b5ec63a`. `prove_divergent_primary.py` passes exact offline, positive and missing-authority compatibility, and saved-only processing with originals preserved. The two original-shaped saved attempts pass `comparison_audit.py --expected-frames 9`; `comparison-audit-exact.log` SHA-256 is `9cb4b221c87bdf1e69defbbc6503912de3e7aa09aeb5cebcd1211f40f3275b2f`. This nine-frame diagnostic is a software proof; the actual 160-frame Native comparison remains unobserved.

`build_marked_fallbacks.py` constructs the same three risk-triggered candidate types for both exact cases: a 0.7 m ego spawn height for a failed road spawn, a 3.5 m/s controller target for turn-target overshoot, and an overview mount shifted 2 m back for marker pixel coverage. `prove_marked_fallbacks.py` passed exact offline and positive/missing-authority compatibility for all six candidates. Construction hashes, triggers, changed knobs and source-bound receipts are in `execution-manifest.json`. The candidates keep each primary case identity, law, actor, 20 Hz/160-frame duration, recording description and camera names/sizes. Selection remains by physical failure trigger, never by expected legal outcome.

`physical_fixture.py`, `lifecycle_fixture.py` and `prove_physical.py` pass complete, incomplete and missing-motion source-shaped outcomes plus ordered Native-exit, owner-release and saved-processing lifecycle for both cases. The two `physical/*-proof.json` receipts bind current construction hashes; they set `actual_native_capture: false`. `marked_delivery_audit.py` independently checks both saved attempts against original source hashes, authority readback, body/trace/frame joins, full decode of all four named streams and absence of legal/physical claims; positive probes pass and negatives reject a stale authority source. Each manifest entry binds its exact positive and negative log and post-capture command. The source-observation mapping now names saved measurements for all seven frozen prompts.

The independent read of the exact LVMC 11.12.020 text found **markers, buttons, and other indications** as separate statutory alternatives. The two current cases construct and compare physical markers only. A button or other indication is not established by the marker fixture or its unverified authority claim. Status therefore remains **partial**, despite the two-case proof chain. Next CPU work: construct exact controlled button and other-indication variants in this cell where feasible, with source-backed authority and physical readback, three tested fallbacks each, complete semantic stage proposals, branch matrix and ordered GPU queue; extend the independent audits and rerun every affected proof. Then run the assignment-scoped strict gate and full batch strict gate. Actual municipal authorization, realized marker/button pixels, full motion and legal direction conformance remain for original recording review; these do not excuse the listed CPU work.

The pinned direct validators `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=4)`, `physical_preparation.validate`, `delivery_handoff.validate_case(..., ['held-out'])`, and `package_compatibility.check_receipts` now pass for both current exact cases. `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete` exits 0; adding `--require-delivery-ready` exits 1 at `preparation.py:276` because the truthful result is partial. The batch has 10,173 returned files under the frozen 10,200 cap after proof-preserving duplicate-log consolidation in already-ready packages, each rechecked with its own scoped strict gate. A complete strict batch rerun is pending; it cannot pass until the remaining assigned partial results are prepared.

Cross-assignment law review: C111644 is a separate frozen, grounded LVMC 11.12.020 intersection/turn/turn-path-marking assignment. Its current six-case plan explicitly pairs follow/depart responses for markers, buttons and other indications, but its result is still partial and has no exact Native proof chain. The button/other-indication alternatives can be assigned to that cell only with a justified shared branch binding and completed CPU packages; this C126064 marker package alone does not prove them. Decide the final branch allocation from both frozen cells without duplicating captures or claiming the current C111644 draft as accepted coverage.

The latest bounded complete strict command, `timeout 300s .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`, completed with exit 1 at `preparation.py:276`: `Preparation acceptance failed: partial/missing packages remain`. The retained `work/_shared/complete-strict-20261112.log` SHA-256 is `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`. This run passed the return inventory precondition; 10,174 files are under the frozen 10,200 cap. The batch remains 35 ready and 16 partial. Resume the listed CPU work and rerun the same strict gate; no external blocker is claimed.

### 2026-11-12 proof-preserving return compaction

Seven byte-identical empty compatibility analysis logs were consolidated with execution-manifest paths repointed to the retained identical bytes. The scoped nonstrict complete gate passed afterward; status remains partial for the already listed CPU omissions.

### 2026-11-12 button and other-indication Native placement step

`marked_course_native.place_course_indications` now constructs source-hashed physical buttons and other indications as separate forms. It requires the claimed authority document, exact intersection/map identity, median-opening relation, sourced intersection polygon, form-specific blueprint inventory and in-junction placement. It checks Native map identity, blueprint selection, spawn success and x/y pose readback, and destroys owned actors on failure. Its result explicitly leaves municipal authorization and visible pixels unverified. This prospective helper does not alter the two previously proved marker bundles; no button/other exact case is yet claimed.

`tests/test_marked_course_native.py` exercises both forms with fake Native blueprint/spawn/readback calls, hash/map/outside-polygon rejection and cleanup after pose mismatch. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v` passes 21 tests; `cpu-tests.log` SHA-256 `58aed195ae6548ee8e6c578fd557ba2bb440348ac3d2be7096f5741507e1aaf1`. The scoped nonstrict complete gate passes.

Status remains **partial**. Next CPU construction is a source-backed button exact bundle using this helper, a source-matched finalizer/diagnostic and primary offline, positive/negative compatibility and saved-only processing; then build the other-indication branch and each case's three risk-triggered fallbacks, physical/delivery/comparison audits and canonical semantic proposals. Original municipal authorization, real pixels and motion remain unverified.

### 2026-11-12 final scoped and batch strict check

The assignment-scoped `worker_check.py --complete` exits 0; adding `--require-delivery-ready` exits 1 at `preparation.py:276` because this assignment result remains truthfully partial. The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` also completed with exit 1 at the same partial/missing-package check. Updated pinned CPU preflight passes; the return is 10,194/10,200 files and frozen assignment statuses are 35 ready / 16 partial. Resume the worker-owned CPU actions above, not a missing-dependency diagnosis.

### 2026-11-12 non-marker Native construction continuation

`marked_course_native.execute_indication_turn` now joins the source-hashed button or other-indication placement/readback to the existing sourced turn targets, four-camera capture and Native motion recorder. It requires matching intersection identities, seals frame counts and releases cameras, recorder and owned indication actors even after failure. `turn_source_recorder.SourceRecorder.record_indication_scene` retains the original authority bytes and form-specific physical positions in `marked_intersection.json` without calling them markers. It rejects a changed source hash, form mismatch and absent readback; it explicitly leaves authorization and visible pixels unverified. The two previously proved marker construction bundles were not altered.

`tests/test_marked_course_native.py::test_nonmarker_native_orchestration_and_original_scene` exercises form-specific retained source, original form rejection, path wiring and resource cleanup with a source-shaped CPU fixture. The full package test command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v` passes 22 tests; `cpu-tests.log` SHA-256 is `33c4dd4153b9f7563e7eef1116a1d7b4bad868d0ba6bdf6f260943514cabd323`. Status remains **partial**. Next, bind this execution path to the button exact case, extend `marked_course_measurement.py` and the finalizer to read `indication_form`/`physical_indications_xy_m`, make a source-matched diagnostic, and run its exact offline, positive/negative compatibility and saved-processing proof before constructing its fallbacks and the other-indication case. Then rerun affected physical, delivery, comparison and semantic proofs. Current marker receipts do not qualify a non-marker form.

`marked_course_measurement.measure` now distinguishes marker, button and other-indication scenes from retained `marked_intersection.json` and exact authority bytes. For non-marker scenes it requires matching original form, inventory count, finite physical readback within 5 cm of sourced positions, and in-polygon placement before measuring the original full-body turn. It rejects a changed form or readback; it does not infer visible pixels or municipal authorization. `tests/test_marked_course_measurement.py::test_button_source_readback_is_measured_as_button` passes its positive and negative source probes. The full CPU suite now passes 23 tests; `cpu-tests.log` SHA-256 is `7fee13bcdd6d3496e1ce4d1917428987428b94b646c0fb5838ea81ee6b8d6119`. The marker exact bundles and saved receipts retain their previous embedded source bytes; this new prospective measurement path has not yet been bound to a non-marker selected case. Continue the exact button bundle and finalizer integration next. Result status remains partial.

### 2026-11-12 return gate after non-marker continuation

Updated environment preflight passes with pinned NumPy, FFmpeg/ffprobe and Lean/Lake 4.28.0. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v` exits 0 with 23 tests; current `cpu-tests.log` and `result.json` bind SHA-256 `7fee13bcdd6d3496e1ce4d1917428987428b94b646c0fb5838ea81ee6b8d6119`. `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete` exits 0. The complete strict command `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain`; the return inventory is 10,194/10,200 files, with 35 ready and 16 partial results. This package remains partial for the exact non-marker case proof path described above. No missing runtime dependency or external blocker is claimed.

### 2026-11-12 exact button course construction continuation

The repaired pinned CPU preflight passes with NumPy 1.26.4, FFmpeg/FFprobe and Lean/Lake 4.28.0 on PATH. `marked_course_finalizer.py` now accepts exact button and other-indication case identities, requires the source-joined physical form to match the selected case, and describes the measured form without a municipal-authority, pixel-visibility or legal finding. `native_runner.py` routes button and other-indication cases through `execute_indication_turn` while retaining the site SHA-256 and lazy CARLA import. Existing marker exact bundles retain their previously proved embedded bytes.

`build_indicated_bundle.py --nonmarker-form button` and `--variant divergent_course` produced two exact button constructions in `execution-manifest.json`. The indicated and divergent construction SHA-256 values are `54d9497a0d9ffba946cc7e8564a8d6c97f0d01d026313f003bd464b06ff3dd80` and `0c6d398c41fe145da48c4d025474a9fac501f671724c5277954b1b0aa5ab2bcf`. Both pinned `runtime.py offline` commands pass with the absolute CPU Python; the log SHA-256 values are `073ca5f4e7bafaca6de83ce31cbfc867441b073541b863dff67dd0f2d3496df2` and `2216242263fc175817f779a07cdf2d05bacec0e64392f9800ccc9cb1607661ad`. The 25-test source suite passes (`cpu-tests.log` SHA-256 `8bb4498668a6e2794d1f4a97967e134e8e912e76daad0501508c7f793074dd96`), including exact non-marker source-form rejection and the two Native preparation variants. The assignment-scoped nonstrict complete gate exits 0.

Status remains **partial**. The two button cases have primary offline proof only. Next, generate form-specific textual original sources and measurement contracts, run each positive/missing-source compatibility and saved-only processing proof, add three distinct risk-triggered fallbacks per case, bind physical and independent delivery/comparison audits, then construct/prove the other-indication pair and canonical semantic stages. Rerun affected marker proofs only if their embedded sources change. The return currently has 10,198/10,200 files; consolidate only verified duplicate, unbound logs before adding more returned proof files. Actual authorization, button pixels, Native motion and legal conformance remain for original review.

The final scoped strict command exits 1 at `preparation.py:276` solely because `result.json` remains partial. A bounded full strict rerun with `timeout 180s` exited 124 without diagnostic output; its empty log is `work/_shared/strict-check-current.log`. This is a local execution bound for that check, not an external dependency and not a readiness claim. The latest completed full strict run still rejects the 16 partial packages. Repository tests (`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s tests -v`) pass 6/6. Continue the concrete source-bound proof chain above and rerun the complete gate after return compaction and further packages.

### 2026-11-12 six-form exact CPU proof continuation

Reread `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/assignment.json` independently of the earlier marker-only plan. The exact text has three form alternatives—authorized markers, buttons, or other indications placed within the intersection—and a whole-turn course obligation. It supplies no numeric deviation cutoff or exception. `case-plan.json` now names six exact cases: indicated and divergent courses for each form, with three controlled comparisons. Source-backed municipal authorization and realized pixels remain unverified; the authority statements in the textual diagnostics are explicitly CPU fixture claims.

`build_button_diagnostic.py` builds source-hashed original authority, physical-readback, body, trace and four-camera diagnostic inputs for the button and other-indication cases. It binds per-case measurement contracts and canonical case drafts. `prove_button_primaries.py` ran positive and missing-original-authority compatibility, then saved-only processing from separately materialized retained sources for both forms and both courses. The current receipts are `button-indicated-compatibility-receipt.json`, `button-divergent-compatibility-receipt.json`, `other-indication-indicated-compatibility-receipt.json`, `other-indication-divergent-compatibility-receipt.json` and corresponding `*-saved-receipt.json`. Each saved receipt reports originals preserved and no missing evidence. These synthetic outputs do not establish authority or physical visibility.

`build_marked_fallbacks.py` constructed three distinct risk-triggered candidates for all six exact cases: spawn height, turn speed, and overview camera placement. `prove_marked_fallbacks.py --button-only` and `--form other_indication` passed exact offline and positive/missing-source compatibility for all twelve new non-marker fallbacks; the previous six marker fallbacks retain their bound proofs. `prove_physical.py` passed complete, incomplete and missing-motion fixture outcomes plus ordered Native exit, owner release and saved processing for all six cases. Its receipts under `physical/` set actual Native capture false. `marked_delivery_audit.py` independently passed each non-marker primary and rejected a stale original authority source. Each manifest entry binds its current positive/negative logs, post-capture command, physical receipt, and construction hash.

`comparison_audit.py` now compares all three physical indication forms with fixed original authority, readback, intersection, capture duration and cameras. It passed the nine-frame saved-source button and other-indication comparisons (`button-comparison-exact.log`, `other-indication-comparison-exact.log`) and rejected changed physical readback (`button-comparison-negative.log`, `other-indication-comparison-negative.log`). The marker comparison and selftest were rerun after this change. The full 160-frame Native comparisons remain unobserved.

Resume commands:

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/build_button_diagnostic.py --form other_indication`
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/prove_button_primaries.py --form other_indication`
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/prove_marked_fallbacks.py --form other_indication`
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/prove_physical.py`
- `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready`

Status is **partial**. Complete the canonical relevance, exact-law template, judgment-observable and cell-binding proposals with a finite source-bound sweep for any judgment phrase; bind and independently review the shared branch matrix and ordered queue, rerun affected exact proofs, then run the scoped strict gate. Do not turn a fixture authority claim, path distance, or compatibility success into municipal, physical or legal acceptance. The local Native run remains an operator action after CPU readiness.

### 2026-11-12 canonical semantic draft and current gate

`proposals/semantic-index.json` now binds source-hashed relevance, exact-law template, two judgment-observable contracts, cell bindings and seven canonical case rows (six selected plus a nonrecording baseline). The two unresolved phrases are the original authority of the indication and whether the realized full-body course disobeys its direction. The observable contracts name retained original authority, readback, body path and four-camera streams without a legal cutoff. The pinned `worker_exchange.semantic_delivery.validate` returns `stage_count: 7`, `selected_cases: 6`, index SHA-256 `ca0982869dd860ca373238771e4a9847cc456cc9cdb01a0f493e5479e34263b2`. Its sweep spec is honestly **incomplete**: a canonical frozen numeric physical grid, every exact sweep member and their full proof paths still need construction. The stage validation is a draft checkpoint, not strict delivery readiness.

The assignment-scoped `worker_check.py --complete` passes after all six exact cases and semantic draft. Assignment-scoped `--complete --require-delivery-ready` still exits 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`, because `result.json` remains partial. The full strict batch command completed with the same status rejection (`work/_shared/strict-check-current.log`, SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`); its file-cap precondition passed. Continue the canonical sweep, branch matrix/queue integration and final independent review before any status promotion. No actual Native capture, municipal authorization, pixel confirmation or legal finding is claimed.

`work/_shared/branch-coverage.json` now binds the exact-text topic to three runnable original-law form branches, each with its indicated/divergent exact case pair and independent comparison. Current SHA-256 is `7e702aad6355d32de109d0541d7a7062d879a482c0a5b29849a508dff1b7003a`. The C126064 scoped nonstrict gate still passes after this binding. The shared independent branch review, canonical finite judgment sweep and ordered queue remain pending; branch mapping alone does not establish those deliverables.
