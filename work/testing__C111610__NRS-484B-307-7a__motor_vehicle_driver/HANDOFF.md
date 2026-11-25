# testing__C111610__NRS-484B-307-7a__motor_vehicle_driver

Status: partial executable construction. Five cases are planned; no recording has been accepted.

Exact law: NRS 484B.307(7)(a) — Where the signal is a flashing yellow turn arrow, displayed alone or in combination with another signal: Vehicular traffic facing the signal is permitted to cautiously enter the intersection only to make the movement indicated by the arrow signal, or other such movement as is permitted by other signal indications displayed at the same time. Such vehicular traffic must yield the right-of-way to pedestrians lawfully within the intersection or an adjacent crosswalk and yield the right-of-way to other traffic lawfully within the intersection.
Assigned branch(es): Pedestrian yield duty.
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-307-7a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

The frozen evidence inventory contains zero accepted recordings. Five exact planned cases now cover arrow-only left turn without another participant, person afoot in adjacent crosswalk, person afoot within intersection, other motor traffic within intersection, and an additional movement allowed by a concurrent indication. `case-plan.json` names four controlled comparisons and exact evidence gaps. The one frozen source topic is mapped to these cases. Presence in a surveyed region is measured; lawful presence, cautious entry, right of way and compliance remain external legal/context questions with no numeric cutoffs.

`native_arrow.py` verifies hashed original map, signal, route and crosswalk sources; checks the surveyed turn and signal facing; lazily spawns ego and a distinct participant with cleanup on spawn failure; and measures frame ordered original arrow exhibition, movement, pedestrian/vehicle classification and polygon occupancy. `turn_control.py` provides conservative approach, hold and turn control. `comparison_audit.py` rejects absent frame histories, changed fixed conditions, incorrect region/class, missing arrow exhibition and unsupported legal verdicts. The Native signal head alone cannot establish a flashing arrow; an externally sourced original aspect packet is an explicit acquisition dependency, still to be wired into the exact runner.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 7 tests; retained `cpu-tests.log` has the SHA in `result.json`. The exact strict assignment gate was rerun and reaches the expected `Preparation acceptance failed: partial/missing packages remain`; retained `cpu-strict-check.log` proves this checkpoint is not ready.

Next CPU work: bind a concrete Native map and official arrow signal source to a runner/config/manifest; implement original aspect acquisition, case-specific finalizer, capture and semantic proposals, per-case offline and source-bound positive/negative compatibility, saved-only processing and independent delivery audit; then rerun exact strict gate. Actual CARLA motion, display realization and camera coverage remain later physical checks. Do not mark ready until the strict CPU gate passes.

## 2026-11-24 original aspect acquisition checkpoint

`aspect_capture.py` now records one injected Native display-adapter packet per 20 Hz tick for 900 ticks, binds official head, facing approach, arrow color/direction, Native head readback, source identity, concurrent indication inventory, contiguous frames and timestamps, and requires observed on/off transitions. It seals the original source and receipt under the attempt directory. The adapter callback must read the actual display or controller; CARLA's coarse traffic-light state is not assumed to identify a flashing arrow. `saved_aspect.py` independently rejects missing, tampered or escaped sources, diagnostic input in delivery mode, and an event history that invents an illuminated arrow during an observed off phase. These modules do not assert physical realization or a legal judgment.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 12 tests. `cpu-tests.log` SHA256 is `6dcd53a0251d5396483675412c1f59f60897ea3f163a321fc1c9d66471bddb2c`. Exact scoped `worker_check.py --assignment testing__C111610__NRS-484B-307-7a__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 is `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`. Exact scoped `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain`; `cpu-strict-check.log` SHA256 is `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

`native_arrow.measure_original` and `comparison_audit.audit` now require observed on/off transitions, and the comparison also holds original arrow timing fixed. Remaining CPU integration: connect the adapter to a concrete surveyed head and exact runner; join the sealed source in the case finalizer and comparison audit; complete semantic proposals, exact case bundles and manifest, source-bound compatibility and delivery audits, and canonical local integration proofs. Physical display and intersection realization remain later checks.

## 2026-11-24 synchronized Native event checkpoint

`event_capture.py` now accepts one callback per Native tick that returns the original display readback and actor-event packet together. Before writing either original source, it checks all 900 frame identities, 20 Hz timestamps, official head and facing approach, concurrent indications, arrow on/off agreement, actor event presence, and flashing transitions. It seals `arrow-aspect-original.json`, `arrow-aspect-receipt.json`, and `arrow-events-original.json`, then reopens the saved pair with `saved_aspect.join_event_history`. The callback is an interface for the later concrete CARLA runner, not a fabricated display source or physical acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-7a__motor_vehicle_driver/tests -v` passed 14 tests; `cpu-tests.log` SHA256 is `fca0a38c6da130c0b10d9f51f57fb56c9071892ae890c15830af87fc1b41234d`. New tests check exactly one tick callback per frame, saved replay, tamper rejection, no overwrite, and rejection of a divergent display packet before source files are written. The remaining CPU integration and exact runner/config/manifest, finalizer, per-case proofs, semantic proposals and independent delivery audit remain unfinished; this assignment stays partial.

The exact scoped static check exited 0 (`cpu-static-check.log`, SHA256 `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`). The exact scoped strict check exited 1 solely because this package remains partial (`cpu-strict-check.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). All 15 returned files are UTF-8 text under 2 MiB with no trailing whitespace, conflict markers or caches.
## 2026-11-23 exact offline arrow bundle checkpoint

`build_offline_draft.py` packages all five exact cases with the existing source-gated construction, turn control, original arrow/actor acquisition and saved audits. Each inline config binds the frozen plan SHA256, exact case construction plan, 900 frames at 20 Hz, four cameras, and required original sources. Its runner validates these bindings and rejects execution without a reviewed original official arrow display, surveyed site and actor sources. `execution-manifest.draft.json` is diagnostic only, not a canonical delivery manifest.

`tests/test_offline_bundle.py` checks all exact case hashes and bundled source copies plus the distinct clear, crosswalk, intersection, vehicle, and concurrent-indication plans. The focused suite passes 16 tests; pinned preflight and scoped static pass. Each `runtime.py offline` exits 0 with `simulation_started: false`:

- `cpu-offline-arrow_clear.log` SHA256 `3d6fb0fc14ef8b20cab8402e0560fcb8cd9bbe71db57508a86f7eb787e69044b`.
- `cpu-offline-arrow_ped_crosswalk.log` SHA256 `67f1acfbc51da0b2f99e291e6f24f38f3cf215eff13dc638deb81bd7a0eb3cef`.
- `cpu-offline-arrow_ped_intersection.log` SHA256 `928a6ce8528c91037fad9b8ca830eebef80f414bfa8b8a67a7ca64318d546bd8`.
- `cpu-offline-arrow_vehicle_intersection.log` SHA256 `a2f7c2b1c48ac96eb76bfcf72fb1702147e1ae27f9419e6dabb3407fc1b98b94`.
- `cpu-offline-arrow_concurrent_movement.log` SHA256 `7b42fc19f7af210bdba3acccae4d1f09fa9688aff550fb1e1d64d538f87212dd`.

Other proof hashes: `cpu-tests.log` `e56a2f19d078e901fc902268ac308ccdc3108619fe85a400f38b85be9a8160bd`; `cpu-preflight-bundles.log` `9833554d8c5c2afd89f639b30fd27688231748ede39f73f7899b8146dc50c91d`; `cpu-static-check.log` `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`; `cpu-strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1, truthful partial).

Next CPU work: source-bind a reviewed original Native official head and flashing arrow display adapter, turn these into canonical executable runners and manifest entries, author semantic proposals and selected-requirement finalizers, then run positive/negative compatibility, saved-only processing and independent delivery/comparison proofs. Physical realization and legal conclusions remain for later original review.

## 2026-11-23 saved arrow finalization checkpoint

`event_capture.py` now seals an `arrow-event-receipt.json` that binds the original actor event digest to the original aspect digest and frame count. `saved_finalizer.py` reopens that source through the independent saved join, requires the exact case and original site source, checks 900 consecutive 20 Hz frames for delivery use, and measures the variant-specific actor region or concurrently permitted movement. It keeps lawful presence, cautious entry and right-of-way verdicts unset. Five new tests cover positive variants, wrong-region rejection, event tampering after receipt, and rejection of diagnostic evidence in original mode.

The five diagnostic bundles now include the finalizer. The draft bundle build, five pinned offline runs, 21 focused tests, pinned preflight and exact scoped static check exited 0. The exact scoped strict delivery check exited 1 with `Preparation acceptance failed: partial/missing packages remain`; status stays partial. Proof hashes are in `result.json`; offline outputs are in `.runtime-work/c111610-owner-output/offline-v2-*`.

Remaining CPU work: independently review a concrete physical Native site and official flashing-arrow display adapter, connect source-gated runners and a canonical manifest, finish semantic proposals and selected-requirement finalizers, run source-bound positive and negative compatibility, saved-only processing and independent delivery/comparison audits. Physical CARLA realization and legal judgments remain unverified.

## 2026-11-24 source-bound saved pair replay

`saved_pair.py` now connects the exact saved finalizer to the existing comparison audit. For a named planned pair it independently reopens each exact site and sealed original aspect/event attempt, reruns finalization and geometry measurement, binds the map/route/crosswalk/signal source hashes, and compares fixed head, approach, camera profile, duration and arrow timing against the declared participant or concurrent-indication difference. It returns both case IDs and site/aspect/event digests with physical acceptance false. The diagnostic fixture does not claim actual flashing-arrow display or legal compliance.

The focused suite passed 23 tests, including source-bound clear-versus-crosswalk replay and rejection of a tampered event file or changed fixed signal source (`cpu-saved-pair-tests.log`, SHA-256 `d76eb7754d6bd311fd69e0b7d064f9a886ed268c591e8713167202a7a4b6982d`). Pinned preflight passed (`cpu-saved-pair-preflight.log`, `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`); scoped static passed (`cpu-saved-pair-static.log`, `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`); exact scoped strict exited 1 on truthful partial (`cpu-saved-pair-strict.log`, `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`). All four logs are SHA-bound in `result.json`; synthetic attempts stayed under `.runtime-work/`.

Remaining CPU construction: reviewed original Native site and flashing-arrow display source, production runner and canonical execution manifest, semantic proposals, per-case positive/negative compatibility and complete four-camera saved delivery audit. The other three comparison pair kinds still need exact source-bound fixture tests. Physical signal/actor/video realization and legal judgment remain unverified.

## 2026-11-24 synchronized original camera continuation

`native_camera_capture.py` now wraps the single Native step callback so each original arrow/aspect and actor-event tick also acquires four same-frame PNG camera bodies. It requires the production four-camera dimensions outside explicit diagnostic mode, stores SHA-bound archives, and removes incomplete archives on a failed tick. `saved_camera_audit.py` independently reopens the sealed aspect/event join, validates archive hashes and full original frame-member maps, then decodes all PNG pixels and dimensions. Neither module claims physical visibility or signal authority.

The 900-frame diagnostic test calls the Native step exactly once per tick, captures and decodes 3,600 original image bodies, rejects an altered archive and rejects a mismatched camera frame while cleaning incomplete archives. The focused suite passed 25 tests (`cpu-camera-tests.log`, SHA-256 `9f34ad43bd1262ed3e3fd32df90f7985f0c03426fe2f39ccb3661e050affadc5`). Pinned preflight passed (`cpu-camera-preflight.log`, `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`); scoped static passed (`cpu-camera-static.log`, `815083c395127cb06ceda824de4084d0e0758516ee679d43861bf23187a18a27`); exact scoped strict exited 1 on truthful partial (`cpu-camera-strict.log`, `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`). `result.json` SHA-binds the four logs. Camera archives and temporary tests remained under `.runtime-work/`.

Remaining CPU: reviewed original head/site/display adapter and production runner, canonical five-case manifest, semantic proposals, per-case positive/negative compatibility, saved delivery integration that combines the arrow finalizer with this camera receipt, and source-bound receipts for all planned comparisons. Physical pixels, motion and legal status remain local review.

## 2026-11-24 exact profile and four comparison replay

The five diagnostic construction bundles now use the pinned overview, approach, reference_corner and driver_reference camera names and include the same-tick camera acquisition and saved audit implementation. All five exact `runtime.py offline` checks pass after rebuilding; logs are `cpu-bundle-nov24-offline-arrow_*.log` with hashes in `result.json`. The case audit previously treated a nonempty list of empty concurrent indication inventories as a positive concurrent signal; it now checks the per-frame contents. All four selected sealed-source comparison pairs replay successfully, including the concurrent movement contrast; the focused suite passes 27 tests (`cpu-bundle-nov24-tests.log`).

Exact scoped static acceptance passes (`cpu-bundle-nov24-static.log`); strict delivery acceptance exits 1 because the result remains partial (`cpu-bundle-nov24-strict.log`). Remaining CPU work is a canonical production runner and manifest, semantic proposals, exact source-bound positive/negative compatibility, saved-only delivery process and independent delivery audit. The reviewed physical site, official flashing-arrow display adapter and real camera/actor realization remain unresolved original-source and later physical checks. No legal verdict is inferred from synthetic packets.

The concurrent-indication case now requires a distinct, original-hashed straight route from the same approach (`native_arrow.verify_site` and `construct_native`); its comparison deliberately varies that route and requires different route-source hashes while holding map, head, approach, crosswalk, signal and frame conditions. A source-tamper test and all four saved pair replays pass. All five offline bundles were rebuilt after the plan and code changes; 28 focused tests, exact static check and expected partial strict check have refreshed SHA-bound logs in `result.json`.

## 2026-11-24 exact semantic stage continuation

`build_semantic_proposals.py` authored relevance, exact-law template, four value-free judgment-observable proposals, cell bindings and five exact case proposals. The phrases retain cautious entry, concurrently permitted movement, pedestrian lawful presence/yield and other lawful traffic/yield as unresolved; physical judgment sweeps remain explicitly incomplete pending a surveyed site, actual official signal controller and feasible actor timing ranges. `check_semantic.py` runs the pinned stage validator and passes all nine stages for five selected cases (`cpu-semantic-stage-check.log`). The exact proposal recording descriptions are now embedded in every diagnostic construction. All five rebuilt `runtime.py offline` checks, 28 focused tests and the scoped static gate pass; the exact strict delivery gate still exits 1 for truthful partial status. Every current command and log hash is recorded in `result.json`.

## 2026-11-24 saved analysis source join

`analysis.py` now joins each exact case finalizer with the independently decoded four-camera archive and requires the same sealed original aspect/event hashes and frame count before emitting selected observational measurements. Its diagnostic fixture test confirms twelve decoded images for a three-frame four-view source and rejects changed archive bytes; delivery mode rejects the diagnostic site. The module leaves physical acceptance and all legal judgments false/unset. The five exact bundles include it, and the latest five offline, semantic-stage, 30-test and scoped static receipts pass (`cpu-analysis-*` logs in `result.json`); the exact strict gate remains partial. A canonical Native runner, full compatibility, saved process and delivery audits still need implementation.

## 2026-11-24 selected measurement contracts

`case-plan.json` now has four selected exact-law requirement dispositions covering official flashing arrow/cautious entry, permitted movement, pedestrian duty and other-traffic duty for all five cases. `build_measurement_contracts.py` emits one four-row contract per exact case, each bound to `analysis.report` and the original site/aspect/event/camera receipt. Pinned `measurement_contract.validate` passes for all five (`cpu-contract-check.log`), and a source-shaped diagnostic report passes `verify_report`; removing `site.json` yields the declared negative error. Draft manifest entries identify the exact contract and analysis entrypoint. Rebuilt semantic proposals and all five offline bundles pass, along with 31 focused tests and scoped static checks. Exact strict delivery check still exits 1 on truthful partial; current receipts and SHA values are in `result.json`.

## 2026-11-24 original ego motion retention

Production `event_capture.capture_pair` now rejects missing or nonfinite original ego speed, brake and heading before writing any aspect or actor source. `analysis.report` retains the by-frame kinematics for review without inventing a cautiousness or yielding cutoff; synthetic diagnostic fixtures are explicitly marked diagnostic and may leave those values null. New tests reject missing/invalid production kinematics, and all 33 focused tests pass. Rebuilt exact bundles, five pinned offline checks, semantic and measurement contract checks, scoped static and expected partial strict receipts are SHA-bound in `result.json` as `cpu-kinematics-*`.

## 2026-11-24 concurrent permission and independent saved source check

`turn_control.command` now selects the alternate surveyed route only when an original concurrent indication and explicit permission source accompany the observed movement; the saved finalizer rejects a concurrent movement without that source. `delivery_audit.py` independently joins the sealed original aspect, actor and four camera archives for the exact case, returning a software source-check result with physical acceptance false. Its diagnostic test rejects a tampered event source. The 36-test suite, five rebuilt offline constructions, semantic and contract checks and scoped static gate pass; the exact strict gate exits 1 because canonical runner/manifest, compatibility, process-saved and physical-completion audit remain unfinished. All current receipts are SHA-bound in `result.json` (`cpu-permission-*`).

The current pinned runtime preflight also passes (`cpu-current-preflight.log`); the exact scoped static check passes and exact strict gate exits 1 on the truthful partial result (`cpu-current-static.log`, `cpu-current-strict.log`).

## 2026-11-24 Native source-gated runner milestone

The old draft runner halted unconditionally. The embedded runner now verifies the exact selected case, hash-bound surveyed site sources and a reviewed original aspect/camera adapter; it ticks CARLA once per frame, checks one aspect, actor and four camera identities, captures 900 original frames, and restores world settings and spawned actors. Native map readback checks route waypoints and adjacent crosswalk against the survey. Fake-world positive, camera mismatch and aspect mismatch tests pass; 39 focused tests and five rebuilt pinned offline bundles pass. This is still diagnostic/offline preparation. Selected compatibility, saved processing and independent physical delivery proof have not passed, so `result.json` remains partial.

## 2026-11-24 source-derived Native seal and saved projection

The Native path now writes a 900-frame trace, original frame map and ego body history from same-tick source packets. It SHA verifies four original camera ZIP archives before and after lossless FFV1 projection, then writes pinned acquisition provenance and a capture seal after world restoration. The saved analysis creates the exact recording channels and a pinned Native result with physical turn assessment from body geometry and heading; no legal or physical-cause verdict is asserted. A 900-frame four-camera projection test, archive-tamper negative, source-copy positive, frame-mismatch negatives and pinned recording-evidence validation pass. Forty-one focused tests and five current offline bundles pass. Canonical selected compatibility, saved processing and independent physical delivery receipts still need CPU proof, so status stays partial.
