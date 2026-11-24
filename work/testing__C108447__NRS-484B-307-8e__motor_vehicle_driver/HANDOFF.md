# testing__C108447__NRS-484B-307-8e__motor_vehicle_driver

Status: partial exact case construction. Six planned case intents and five controlled comparisons; no recording has been accepted.

Exact law: NRS 484B.307(8)(e) — Where the signal is a steady red signal alone: Vehicular traffic facing the signal may not proceed on or through any private or public property to enter the intersecting street where traffic is not facing a red signal to avoid the red signal.
Assigned branch(es): Property bypass at an intersection.
Cell: C108447 (intersection, bypass_signal, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

- `case-plan.json` now covers private and public property bypass, ordinary roadway crossing, non-red approach, red destination, and separately sourced other purpose. Five comparisons reuse the private bypass reference. The frozen accepted evidence inventory has zero recordings; each proposed case maps to that gap.
- `property_route.py` checks original source seals, parcel authority and polygon traversal (including a segment that crosses without an interior sampled point), frame-joined approach and destination signal states, street identity, vehicle class, and purpose as a separate sourced fact. It returns observed predicates and no legal verdict.
- `route_controller.py` validates a source-bound connector in either approach direction and computes bounded low-speed controls. Its CARLA import is lazy. `comparison_audit.py` rejects missing source seals, missing deliberate changes and undeclared fixed-condition changes.
- `.venv-cpu/bin/python runtime.py preflight` passed after the pinned environment update. `.venv-cpu/bin/python -m unittest discover -s work/testing__C108447__NRS-484B-307-8e__motor_vehicle_driver/tests -v` passed 19 CPU tests (`cpu-tests.log`). `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete` passed (`assignment-check.log`).
- Exact strict command: `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete --require-delivery-ready` remains partial (`strict-gate.log`). The general strict exception does not establish completion.
- Continue CPU construction: bind an original Native map/property-authority packet and traversable connector, write the exact runner/config/construction bundles for all six cases and per-case finalizers, semantic proposals, offline and positive/negative compatibility proofs, saved-only and independent delivery proofs, then canonical execution and comparison receipts. Do not infer avoidance purpose from path shape or infer a non-red destination from a green assumption. Actual body route and camera realization are later GPU checks.

## 2026-11-24 original Native capture checkpoint

- `native_capture.py` records a 20 Hz, source-identified ego body path plus both per-frame device state histories from an exclusive Native world and a reviewed map packet. It rejects unjoined destination streets, missing purpose or vehicle-class sources, missing signal identities, duplicate frames and unobserved entry; cleanup commands braking even on failure. The CARLA control import remains lazy through `route_controller.apply_carla_control`. Capture receipts explicitly make no physical acceptance claim.
- `property_route.py` now checks every body/signal frame join and the approach red-alone state across the captured route; a mid-route phase change leaves the observed activation false. No legal verdict is produced.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C108447__NRS-484B-307-8e__motor_vehicle_driver/tests -v` exit 0; `cpu-tests.log` SHA256 `40d954e41ff795c7bb7c49eb22e802fc25ebd4b9821071b554b3fe23093a0f54`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete` exit 0; `assignment-check.log` SHA256 `98c73331c9ba5bcabd7c402e1028fdda6681d78d0a90c2626a7f8c461529d8a3`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete --require-delivery-ready` exited 1; `strict-gate.log` retains the expected partial-package rejection. No ready claim.
- Next: select and seal the original map/parcel authority source; wire the capture into each of the six exact case bundles and the four-camera Native frame map, then run exact offline, compatibility, saved-only, semantic and independent delivery proofs. The current CPU capture does not itself establish the parcel classification, visibility, or successful CARLA motion.

## 2026-11-24 four-camera and independent saved-source checkpoint

- `native_capture.py` now retains all 900 planned 20 Hz body and signal observations even after first destination entry; it brakes after entry and on every exit. The first entry frame remains separate from the last capture frame. An optional original camera callback writes `overview`, `approach`, `property`, and `destination` PNG archives and a per-frame source-hashed image map. Missing/corrupt camera bytes fail capture; no physical success claim is emitted.
- `saved_delivery.py` independently rejects diagnostic sources, wrong exact case, tampered map/trace/frame-map/archives, frame gaps, missing 20 Hz body or signal joins, incomplete four-camera inventory and unmatched images. It decodes every original PNG and then invokes the source-sealed property-route observation checker. This is a saved software audit, not a legal verdict or physical acceptance.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C108447__NRS-484B-307-8e__motor_vehicle_driver/tests -v` passed 35 tests in `cpu-tests.log`, including a 900-frame capture, four-camera archive production, full pixel decoding and negative tamper/diagnostic/case/frame/camera paths. The log SHA256 is recorded in `result.json`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C108447__NRS-484B-307-8e__motor_vehicle_driver --complete` passed; `assignment-check.log` and its SHA256 are recorded in `result.json`. The same command with `--require-delivery-ready` exited 1 and is retained in `strict-gate.log`, because status is still partial.
- CPU work remaining: bind an authoritative original parcel/map source, all six exact runner/config/construction bundles, source-hashed semantic proposals, exact offline and positive/negative compatibility receipts, saved-only postprocessing receipts, independent per-case delivery receipts and canonical integration. The current media interface can produce original sources, but neither the current fixture nor its tests establish actual CARLA traversability or camera visibility.

## 2026-11-24 original map binding and proof refresh

- `map_binding.py` accepts an original OpenDRIVE file and separately sourced parcel authority JSON, then verifies their mutual SHA256 join, coordinate/map identity, distinct public/private parcel classifications, selected destination street and connector geometry, plus an explicit source review input. It never certifies the authority's truth from a fixture. `saved_delivery.py` rechecks original OpenDRIVE and authority seals in the saved attempt before analyzing observations.
- Focused tests now pass 41/41 in `cpu-tests.log`; scoped static passes in `assignment-check.log`; exact scoped strict exits 1 in `strict-gate.log` because the package remains partial. The passing proof hashes are refreshed in `result.json`. No actual parcel authority source or CARLA recording is present in this worker package.

## 2026-11-24 original connector traversal guard

`map_binding.py` now rejects zero-area parcel polygons and source-bound connector routes that do not cross the selected property interior. The segment-intersection check accepts a crossing between sampled waypoints; a connector that stays entirely outside fails before a Native construction can use it. Two new tests cover the crossing, outside route and degenerate polygon. The 43-test assignment suite passes. This source-shaped CPU proof does not certify parcel authority or actual CARLA traversability.

The exact scoped static gate exits 0; the exact scoped strict gate exits 1 on truthful partial status. Next worker-owned CPU work: retain independently reviewed authoritative original parcel/map bytes and traversable connectors; build six exact source-bound runner/config/construction bundles; run pinned offline, positive/negative compatibility, saved-only and independent delivery/comparison proofs; complete semantic proposals and ordered integration. No frozen input, runtime, batch or shared files were edited; no Git command was run.

## 2026-11-24 case-specific observation and roadway construction checkpoint

`case_observation.py` now checks the six exact case contrasts against retained original route, phase and separately sourced purpose observations. `saved_delivery.py` runs it after source and full-pixel verification. `property_route.py` evaluates the approach red-alone phase through destination entry; retained post-entry braking frames no longer rewrite the movement condition. `map_binding.py`, `route_controller.py` and `native_capture.py` support a separately source-bound ordinary-roadway comparator route and reject any crossing of an inventoried parcel. Bidirectional route, all-six positive and wrong-difference negative CPU tests pass. These are software checks, not physical or legal findings.

Pinned preflight, 58 assignment tests and scoped static passed; exact scoped strict still exits 1 on truthful partial status. See `nov24-case-observation-*.log` and SHA256 entries in `result.json`. Next: select and independently review authoritative map/parcel bytes and both connector/roadway routes; create the six exact runner/config/construction bundles, source-hashed semantic proposals, offline and positive/negative compatibility, saved-only, independent delivery/comparison and canonical integration receipts.

The independent `comparison_audit.py` now binds all five planned comparisons to exact baseline/contrast case IDs and expected observed classes/states/purpose. It rejects wrong pairs or values before checking fixed conditions and seals. Positive tests exercise all five pairs; negative tests reject extra changes and false case/value binding. This is a CPU packet proof; an actual saved-attempt comparison still needs case-specific source receipts.

The map binder now requires the connector and optional ordinary roadway routes to match the sealed original authority JSON. The saved auditor independently rechecks those joins, rejects missing connector geometry, and requires a roadway route for the ordinary-crossing exact case. Source-shaped positive and tampered-route negatives pass in the 58-test assignment suite.

## 2026-11-24 six-bundle, diagnostic and semantic checkpoint

- `build_bundles.py` now emits six exact inline source-sealed constructions and `execution-manifest.draft.json`. Each has a 45-second, 20 Hz, four-camera profile and CPU `runner.py --check`; the entrypoint accepts owner-supplied original Native objects for capture. The manifest remains a draft because no authoritative physical site or original capture has been accepted.
- All six constructions passed `runtime.py offline` materialization. `draft-offline-receipts.json` binds construction and log hashes. The permitted receipt basename avoids the runtime validator's generated `offline-` directory rule. Scratch and materialized files were written only under `.runtime-work/`.
- `build_diagnostics.py` generated six explicit diagnostic-only fixture recipes and specifications. Each passed `runtime.py fixture` materialization; `prove_diagnostics.py` produced a six-case source-observation proof. `diagnostic-receipts.json` binds their source and log hashes. These fixtures do not establish parcel status, signal authority, original camera pixels or legal outcome.
- `build_semantic_proposals.py` generated the exact relevance, template, avoidance-purpose observable, binding and six-case proposal chain with stage hashes in `proposals/semantic-index.json`. Runtime `semantic_delivery.validate` passed with six selected cases and descriptions matching the constructions. The purpose judgment sweep is marked incomplete pending original source and physical feasibility; no value or verdict is supplied.
- The refreshed 62-test assignment suite passes, covering bundle and receipt hashes. Scoped static and strict outcomes are recorded in `result.json`. Remaining worker-owned CPU work includes accepted original map and parcel authority, six physical source-bound attempts, positive and negative compatibility, saved-only processing, independent per-case delivery/comparison receipts and final canonical integration. Status remains partial.

## 2026-11-23 source-confined six-case bundle checkpoint

`saved_delivery.source_file` now rejects traversal components and symlink aliases for original map, parcel authority, trace, case, frame map and camera archives. The added negative test replaces a trace source with a byte-identical symlink and then attempts a `nested/../trace.json` reference; both fail before any source or pixel conclusion. This preserves the saved attempt boundary and does not certify parcel authority, physical motion or legal avoidance purpose.

All six exact inline bundles were regenerated to include the updated auditor. Their construction hashes and refreshed exact offline proof logs are bound in `draft-offline-receipts.json`. Pinned preflight, all 63 focused tests, all six exact offline checks and scoped static exited 0; exact scoped strict exited 1 on truthful partial status. New log hashes are in `result.json`. Remaining CPU work includes positive/negative compatibility, per-case saved processing and independent delivery/comparison receipts, authoritative reviewed Native map/parcel selection, and canonical integration.

## 2026-11-24 original media inventory and profile guard

`saved_delivery.py` rejects duplicate ZIP member names even when the archive hash is refreshed. On a full 900-frame attempt, it also enforces the 1920×1080 overview and 1280×720 detail camera profile after full PNG decode. Two tests cover a resealed duplicate and production dimension mismatch; diagnostic short episodes retain small images for CPU fixture speed and cannot claim delivery. Six exact inline constructions were regenerated, all six offline materializations passed and `draft-offline-receipts.json` now binds the new construction and log hashes.

An exact private-bypass `runtime.py compatibility` attempt exits before analysis because the draft manifest has no `measurement_contract` entry; `cpu-compat-private-v1.log` records this precise CPU gap. Sixty-five tests, pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Canonical measurement contracts and analysis, positive/negative compatibility, saved-only and delivery receipts, and authoritative parcel/map review remain worker-owned.

- `cpu-compat-private-v1.log` SHA256 `5a56a170eea0bedbe6a2eba190489c9db69fca8359b46bd56479d8d32d17502e`; exit 1.
- `cpu-zip-build.log` SHA256 `6c09a898aaf9078f03f6e7ac15cf243093041c9e6135fa96e360b71d57e728cf`; exit 0.
- `cpu-zip-tests.log` SHA256 `3f90206aeced29db13c660fca6ad3308f4251d6619e23d894caba20e27b780eb`; exit 0.
- `cpu-zip-preflight.log` SHA256 `ea0de4773400feca113e45df889b420e1e0d314919c6c5dce4d5203e19bf1e9d`; exit 0.
- `cpu-zip-static.log` SHA256 `98c73331c9ba5bcabd7c402e1028fdda6681d78d0a90c2626a7f8c461529d8a3`; exit 0.
- `cpu-zip-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; exit 1.
- `cpu-zip-offline-private_bypass.log` SHA256 `c1735749e6d714a44fb95fde75eaefb7df0669b9f063e7b6386b1dfad8b520a4`; exit 0.
- `cpu-zip-offline-public_bypass.log` SHA256 `a299b02d9e2565b102a47d4866b5c643beb9c8f92a93b378c84b6cf528e4dc48`; exit 0.
- `cpu-zip-offline-ordinary_crossing.log` SHA256 `79de09db64ecc94ff87b61793aeda90b0a660a34fd2af1ba6dead331de93f827`; exit 0.
- `cpu-zip-offline-no_approach_red.log` SHA256 `4e78f485e11a516d4cf543778295b1c556e38893d5ca35e40d3c7ac87014c104`; exit 0.
- `cpu-zip-offline-destination_red.log` SHA256 `697450a4058b9a424d6e8b877ff6bcf9ca6c7493245d76044102461e82d64de1`; exit 0.
- `cpu-zip-offline-other_purpose.log` SHA256 `3536fbefd4e8c042135fcffb135d0b10d82df09ce15442ec72a45fc10681ad31`; exit 0.

## 2026-11-24 original Native clock readback checkpoint

`native_capture.py` now checks the owner-supplied world is synchronous with a 0.05-second fixed delta, reads the CARLA snapshot after each tick, requires its frame identity to match the tick and all frames to be consecutive, and uses the original elapsed timestamp for both the ego trace and four-camera frame map. It rejects a 20 Hz clock drift greater than 2 ms before returning a capture. The tolerance verifies sampling integrity; it is not a legal threshold. Fake-world tests cover a skipped frame, drift, wrong world setting and nonzero original clock origin. Saved delivery already independently verifies frame-map and ego timestamp joins.

All six exact source-sealed constructions and semantic proposal bindings were regenerated. Six pinned `runtime.py offline` checks passed and their new construction/log hashes are sealed in `draft-offline-receipts.json`. The 66-test focused suite, pinned preflight and scoped static passed; exact scoped strict exited 1 on truthful partial status. This does not establish parcel authority, Native motion, camera visibility or avoidance purpose.

SHA-256 bound current proof logs:

- `cpu-clock-tests.log`: `acf99616d24979fa9ffb16be90e2bd7bdf85c666ac0589a6ad70460b45e05890` (exit 0)
- `cpu-clock-preflight.log`: `68756cdc19ea16da6617aa81ea800b545f7d77cea965774616428ba2afd07746` (exit 0)
- `cpu-clock-offline-private_bypass.log`: `82b907f37a3a974dcd8ee6abbbbe7b0cb87ef24ed91aac183284043072caae90` (exit 0)
- `cpu-clock-offline-public_bypass.log`: `5c816081e069732c6af0873eb11749c23f839d421b0c14f7d1abe3f89252aeee` (exit 0)
- `cpu-clock-offline-ordinary_crossing.log`: `be0436433834047b26a9efafcf89188e2b16fe9fd2432dfa02f17382c98d8b1c` (exit 0)
- `cpu-clock-offline-no_approach_red.log`: `0cfcc1fa73b1af8fee6f6f71983b0e0ccaba10434458b30095f49c01fcd7e0e7` (exit 0)
- `cpu-clock-offline-destination_red.log`: `dea2d3ffeb2aa7b764f6c247bd224152d29768183a5101490d2a2daf3dbb629a` (exit 0)
- `cpu-clock-offline-other_purpose.log`: `976e61e0f1cf24f6c285705826793df1587325a8b72e5522f2bc4cf0cf8f777f` (exit 0)
- `cpu-clock-static.log`: `98c73331c9ba5bcabd7c402e1028fdda6681d78d0a90c2626a7f8c461529d8a3` (exit 0)
- `cpu-clock-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

Next CPU work: add selected-requirement measurement contracts and executable analysis entrypoints to the six bundles, then run source-shaped positive/negative compatibility and process-saved, independent delivery/comparison receipts. Select and independently review authoritative original parcel/map material before physical capture. Preserve partial until exact scoped strict passes.

## 2026-11-24 selected measurement checkpoint

`case-plan.json` now names five selected source-observation requirements for the exact red-alone approach, property traversal, non-red intersecting street, separate avoidance purpose and motor vehicle route. `build_bundles.py` generates a six-case exact measurement contract for each selected case and includes `analysis.py` in every refreshed inline construction. The analysis opens the diagnostic authority/OpenDRIVE/map/trace sources, verifies their joins, calls the case observation audit, and emits five case-specific source-hashed measurements without a legal or physical verdict. Tests validate all six runtime measurement contracts and analysis reports against exact input bytes, and reject a missing or mutated authority source and foreign case.

All six refreshed pinned offline checks, 69 focused tests, preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. A new pinned private-bypass compatibility attempt passed contract validation and fixture materialization, then failed in four-view preparation because the current diagnostic fixture lacks `video_frames.jsonl` (`cpu-measurement-compat-private.log`). The next CPU slice must add a source-consistent frame map and capture evidence to the diagnostic recipe, then produce canonical `result.json` and run positive/negative compatibility and saved delivery. Original parcel/map authority and actual Native motion remain unverified. Exact commands, exit codes and SHA-256 log hashes are in `result.json`.

## 2026-11-24 four-view compatibility progress

The Native capture, saved image audit, runner, bundle tests and diagnostic recipe now use the pinned camera identifiers `overview`, `approach`, `reference_corner` and `driver_reference`. The last two retain the parcel-boundary and destination-entry view strategies. Diagnostic specifications include a 20-frame source-shaped `video_frames.jsonl`; all six materializations and source-observation proof were refreshed. The camera-name change was propagated into all six exact inline constructions and semantic proposal hashes.

All six refreshed pinned offline checks, 69 focused tests, preflight and scoped static pass. Pinned private-bypass compatibility now composes four-view video and runs the five source-hashed measurements in `analysis.py`; it stops at missing canonical `result.json` (`cpu-camera-compat-private.log`). Exact scoped strict remains truthful partial. The next CPU slice is a source-honest canonical result/finalizer with trace/frame-map/evidence join, followed by positive and missing-source negative compatibility, process-saved and delivery audit. No diagnostic media establishes parcel authority, purpose truth or physical motion. Commands and SHA-256 logs are in `result.json`.

## 2026-11-24 current-runtime result and saved-source checkpoint

`analysis.py` now writes canonical `result.json` from the retained ego trace, original frame map, four camera files, and five source-hashed property measurements. It rejects a mismatched preexisting converter trace and never asserts physical or legal completion. `native_capture.py` samples the original velocity vector for converter speed evidence. The diagnostic recipe includes pinned-runtime shaped capture graph files, a source-sealed synthetic map and authority, four 9-frame camera streams, and matching frame identities. These are synthetic CPU fixtures only.

All six exact current-runtime fixture materializations, offline commands, and compatibility commands passed. Every compatibility proof includes selected measurements, Native/Core/Lean/render/final video stages, and a negative removal of `authority.json`. Receipts and logs are in `diagnostic-receipts.json`, `draft-offline-receipts.json`, and `proof-<case>-compat-{receipt.json,analysis.log,negative.log}`. All six `runtime.py process-saved` commands passed with original hashes unchanged, joined frames, decoded final video, and no physical acceptance claim; `saved-processing-receipts.json` binds those logs. The independent `diagnostic_delivery_audit.py` passed all four diagnostic video pixel streams and exact map/trace/frame source joins for all six cases; missing-authority negatives failed as expected. `diagnostic-delivery-audit-receipts.json` binds those logs. The production PNG archive audit in `saved_delivery.py` has positive and adversarial unit tests, but no original Native archive exists here.

The 69 assignment tests, pinned preflight, and scoped `worker_check.py --complete` pass. Exact scoped `--complete --require-delivery-ready` exits 1 because `result.json` truthfully remains partial (`proof-final-*.log`). Required source inputs still absent: an authoritative reviewed parcel/public-private classification and connector route tied to the original Native OpenDRIVE map, original red-alone approach and destination signal observations, separately evidenced avoidance purpose, and original full-body/camera motion. Without these, physical outcome/lifecycle and production delivery acceptance receipts cannot be honestly asserted. The selected manifest remains `execution-manifest.draft.json`; it must not be promoted as ready without source-bound fallback/candidate, physical, saved-only, and delivery acceptance contracts.

## 2026-11-24 selected-manifest CPU continuation

- Six primary and six slower-controller fallback constructions were rebuilt and passed current-runtime offline and positive/negative compatibility checks. The fallback responds to measured route endpoint overshoot; no statutory threshold was added.
- `execution-manifest.json` now selects all six cases, binds current constructions, offline and compatibility receipts, Native handoff, physical preparation and diagnostic independent delivery probes. Root `config.json` and `construction.json` describe the first selected case.
- Six selected-manifest diagnostic compatibility attempts were processed through `runtime.py process-saved`; each preserves originals, joins frames, decodes final video and explicitly declines legal or physical acceptance. `selected-saved-processing-receipts.json` binds the selected manifest hash.
- Five exact comparison probes checked source seals, common device IDs, camera profile, duration, map and actor, plus the planned changed variable. Each negative control changed an approach device ID and was rejected. Receipts are diagnostic only.
- 77 focused tests and the scoped complete static gate passed. The scoped strict gate exited 1 because `result.json` remains truthful `partial`. Original reviewed parcel/map authority, actual Native body path and original camera pixels have not been supplied, so the physical and production delivery audits cannot claim acceptance.
- Scratch attempts and temporary files are under `.runtime-work/c108447-resume/`. Every returned assignment file is below 2 MiB with no trailing whitespace or blank EOF.

## 2026-11-24 original-attempt packaging and source audit closure

- Added `prepare_delivery.py` to turn an owner-recorded 900-frame trace, frame map and four PNG archives into a self-contained `delivery-bundle.json`. It rechecks `map_binding.bind`, copies the exact OpenDRIVE and reviewed parcel authority into the attempt, and seals every retained relative path. The command is `python prepare_delivery.py --attempt ATTEMPT --map-packet REVIEWED_PACKET --case EXACT_CASE --property-id PROPERTY_ID`; run `delivery_audit.py` on the resulting bundle. No physical result is inferred during packaging.
- Fixed `property_route.analyze_files` to resolve the sealed authority relative to the retained map packet. The previously absolute map-binding references would have failed the saved auditor after capture; the new 20-frame packaging-to-delivery-audit test passes.
- The independent saved auditor now checks authority format, map name, coordinate frame, street ID, parcel classes and boundaries as well as routes. A resealed private-to-public packet is rejected.
- Rebuilt six primary and six fallback inline constructions with packaging and audit source included. All twelve current-runtime offline and positive/negative compatibility proofs passed; six draft and six selected-manifest saved-only diagnostic runs passed with originals preserved, frame joins and final decode. Five current diagnostic fixed-condition comparison pairs passed with negative controls. Eighty focused tests and the scoped complete static gate passed.
- Exact assignment input inventory contains only `assignment.json`, `evidence.json`, `witnesses.json` and `judgment_ranges.json`. No reviewed original parcel authority, OpenDRIVE parcel site or original camera/ego recording is present. Keep `result.json` partial until those original observations pass `delivery_audit.py`; the diagnostic fixtures are not physical evidence.

## 2026-11-24 original-pair comparison audit

- Added `comparison_delivery.py` to rerun full original-source, four-camera pixel and physical-route checks on both saved attempts before `comparison_audit.audit_planned` checks one deliberate difference and fixed map, actor class, camera profile, duration, signal identities and other case conditions. It is included in each inline construction.
- The 20-frame original-shaped pair test passes; a resealed changed approach-device ID is rejected. The six current selected-manifest saved-only diagnostic runs and all twelve primary/fallback offline and compatibility runs passed after the source addition; 82 focused tests and the scoped complete static check passed.
- For physical review, run `comparison_delivery.py --comparison ID --left-attempt DIR --left-bundle FILE --right-attempt DIR --right-bundle FILE --output FILE` after each original attempt passes `prepare_delivery.py` and `delivery_audit.py`. Default 900 frames. No real original pair exists in the exact frozen inputs, so original-pair acceptance remains pending and result status is partial.

## 2026-11-24 reviewed-site and Native owner handoff

- Added `site_review.py` to require a separate original-site review receipt naming the exact OpenDRIVE and parcel authority hashes, map/frame/property identity, reviewer, source record and reviewed decision. It rebinds the source routes and parcel geometry with `map_binding.bind`. A stale hash or pending review fails before capture.
- Added `native_dispatch.py` to compare the live owner-held Native map name and OpenDRIVE bytes with the reviewed source, run `runner.capture_original` inside the exclusive owner context, demand restoration and actor/sensor release readback after exit, then package and independently audit the saved attempt. It retains and rechecks the review receipt against the copied map and authority after packaging. Mismatched live maps exit the owner context without capture; failed release readback or changed saved source prevents pixel auditing. These modules are assignment-local CPU acquisition code included in all twelve selected inline constructions.
- The bundled `runner.py` now exposes the runtime `--output-dir --host --port` capture CLI and loads an assignment-local Native owner module supplied through `C108447_NATIVE_OWNER_MODULE`. `canonical_bridge.py` converts owner-exported original trace and four PNG camera archives to canonical trace/frame tables and four encoded video streams, then seals the capture with restoration readback. The site review, dispatch and bridge are embedded in all twelve constructions. No reviewed original map/parcel source, Native owner module or original recording is in the four frozen assignment input files, so status remains partial.

## 2026-11-24 canonical capture bridge and selected replay

`runner.py --output-dir --host --port` now implements the canonical runtime capture handoff. It validates the separately reviewed original site, enters the supplied Native owner context, captures original body and camera observations, checks release/restoration readback, packages and independently audits original pixels, and bridges the resulting owner graph to runtime capture-seal inputs. The owner module interface is `owner_factory(host, port, packet, case_id)` and `export_graph(owner, root, attempt, capture)`; the latter must provide owner-origin capture manifest, evidence and Native frame rows. If those inputs are absent, the runner records failure in `native-run-status.json` and exits. No diagnostic fixture is accepted as an original source.

All six primary and six fallback refreshed offline and positive/negative compatibility proofs passed after embedding the bridge. All six selected-manifest diagnostic saved-only replays passed against the final selected manifest hash, with preserved originals, frame joins and final decode; `selected-saved-processing-receipts.json` binds their logs. The 89-test focused suite and complete scoped static check pass. The exact strict assignment gate still exits 1 because `result.json` truthfully remains partial. Physical original-source delivery and the five original-pair comparisons require reviewed OpenDRIVE/parcel material, a Native owner adapter and actual original frames absent from the exact frozen inputs.

## 2026-11-24 Native graph frame binding

The canonical bridge now checks every owner-exported Native graph frame and evidence frame/time against the original body and four-camera frame map before copying sources or encoding video. A shifted graph frame fails before a canonical trace or seal is written. After this change, all twelve refreshed offline and positive/negative compatibility proofs passed, all six selected-manifest diagnostic saved-only replays passed against selected manifest SHA-256 `7756a3b8b6c711732cf1f2972215b78b6f3eff41639be89f197d0f830d112675`, 90 assignment tests passed, and the scoped complete static check passed. The exact strict assignment gate still exits 1 on truthful partial status pending original physical sources and pixels.

## 2026-11-24 canonical bridge success-path proof

A two-frame source-shaped CPU test now feeds four hash-bound PNG archives, synchronized original body and camera rows, and matching Native graph/evidence rows through the canonical bridge. It verifies four encoded MKV streams, two canonical trace/frame rows and one seal call. The same test exposed unclosed ffmpeg stderr pipes; the bridge now closes both process pipes after success or failure. All twelve refreshed offline and positive/negative compatibility proofs pass after this source change; all six selected-manifest diagnostic saved-only replays pass against manifest SHA-256 `b1cb562320f991b78c13b4af813c1874b1dccdd10416ff34397ac0f25bd7bbe9`. The 91-test assignment suite and scoped complete static check pass. The exact strict gate exits 1 on truthful partial status; original site authority and physical pixels remain to be captured.

## 2026-11-24 Native capture failure cleanup proof

A synthetic owner now raises during the live capture callback. The dispatch test verifies its context exits and release path runs, while saved processing never starts. This covers a sensor or capture exception in addition to the existing live map mismatch and failed restoration refusals. All 92 assignment tests and scoped complete static check pass; the exact strict gate exits 1 because physical original-source delivery remains unverified.
