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
