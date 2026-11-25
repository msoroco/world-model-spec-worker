# C111125 / NRS 484B.307(8)(d) / cycle or scooter operator

Status: **partial CPU construction, measurement and saved-processing checkpoint**. The fixed assigned witness is a bicycle proceeding straight after failed detection. Zero accepted recordings are listed in the frozen evidence inventory. No physical or legal outcome is claimed.

## Exact cases and comparisons

`case-plan.json` selects five exact cases: `two_cycles_failed_detection` (reference), `one_cycle`, `signal_changes`, `no_prior_stop`, and `fails_to_yield`. The four comparisons isolate observed complete cycle count, failed detection versus a changing signal, antecedent stop, and yielding to a signal-directed participant. Every case retains the C111125 intersection, bicycle, straight maneuver and official traffic light. No numeric legal threshold is invented; the two complete cycles are the statute's count. The packet records all phase transitions because the meaning of the applicable device's cycle boundary still needs original source and legal review.

The statute also names device malfunction, pedestrians and other traffic, three other road-user types, and right/left turns. The assigned witness fixes bicycle, failed detection and straight. The malfunction alternative and separate pedestrian/traffic yield contrasts could be added in this same cell after source review. Right/left turns conflict with this cell's fixed straight maneuver and need lead review of existing compatible cells; this package does not claim those alternatives covered.

## Implemented CPU path

`signal_trial.py` verifies source hashes for map, official device, detector link and bicycle blueprint packet before planning. Its CARLA-lazy `spawn_case` calls the injected Native world blueprint library, reads back the spawned blueprint and actor ID, installs a detector/device policy by injected adapter, and destroys an owned actor on failed setup. `control_step` requests stop, creep or straight travel from current readbacks while preserving each deliberate case contrast. Requested behavior is separate from measured behavior.

`measure_attempt` requires sealed original Native, device, detector and geometry files; the per-frame rows must exactly join those files. It rejects stale hashes, absent channels, discontinuous frames, non-20 Hz timestamps, wrong actor/device/map identity, missing straight entry and nonmonotone route. It measures stationary behavior before the source-bound stop boundary, observed red through entry, sensor-zone occupancy versus output, complete observed green/yellow/red rotations, and directed-participant conflict at entry. The output has no legal verdict or physical acceptance. `comparison_audit.py` independently checks exact pairs, fixed source identities, original bindings, intended measured differences and the reference prerequisites.

`tests/test_signal_trial.py` and `tests/test_comparison_audit.py` cover positive construction, source rejection, all five measurements, actor cleanup and all four comparisons. The fixtures are synthetic CPU packets and do not prove Native execution or video visibility.

`saved_attempt.py` is a CARLA-free saved attempt processor and CLI. It reads an exact `attempt.json` receipt, verifies the packet hash and its four original Native/device/detector/geometry source hashes, checks capture completion, actor readback, detector/device policy authority, frame count and case identity, and then invokes the original measurement path. Its default mode rejects diagnostic fixtures. Diagnostic mode is explicit, retains `diagnostic_fixture: true`, and always returns `physical_acceptance: false` and `legal_verdict: null`. The CLI writes measurement output outside the sealed attempt tree. `tests/test_saved_attempt.py` exercises the CLI plus source tampering, identity, incomplete Native exit, path escape and frame-count rejection. This is a CPU saved-processing component, not the full runtime `process-saved` delivery path.

## Proofs and exact gate

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator/tests -v` passed 13 tests. `cpu-tests.log` SHA256 `31c0e06306808a77360f72834458bda3cd7f831d9a9b243e88efb85e896bf0e6`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete` passed static checks. `assignment-check.log` SHA256 `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete --require-delivery-ready` failed, as expected for truthful partial status, at `Preparation acceptance failed: partial/missing packages remain`. See `strict-gate.log`.

## Exact remaining CPU work

Source a Native C111125 map/device/detector packet and an actor blueprint that substantively represents a bicycle with rider; make the policy adapter observe the detector-to-signal causal link. Bind the capture-time seal and saved processor to the runtime process-saved finalizer. Author full canonical semantic proposals and `semantic-index.json`, exact per-case configurations, source-hashed diagnostics, manifest, offline and positive/negative compatibility receipts, runtime process-saved integration and independent delivery acceptance. Assess whether malfunction and separate participant variants remain within the assigned branch. For the fixed straight cell, refer turns to the lead's branch binding review. Keep status partial until the exact strict gate passes. Then run the prepared GPU queue locally for actual motion, sensor behavior, camera visibility and full video review.

## 2026-11-23 synchronized source-capture checkpoint

`native_capture.py` now accepts post-tick original readbacks through an injected adapter, seals 20 Hz frame identities, writes separate original Native/device/detector/geometry streams, and stores four synchronized PNG camera archives named for the prospective capture profile (`overview`, `approach`, `reference_corner`, `driver_reference`). Each frame records its original camera member and pixel hash. A completed `attempt.json` appears only after all frames and archives have been written and the caller supplies `native_exit_code=0`; a failed exit is rejected before the attempt directory is created. For non-diagnostic capture the writer requires the profile's 1920x1080 overview and three 1280x720 detail images. It does not instantiate a CARLA world or assert physical success.

`saved_media_audit.py` independently reopens the sealed attempt, streams the archive SHA256 checks, verifies contiguous 20 Hz frame identities, joins all four camera members to their per-frame hashes, fully decodes each PNG and checks consistent/profile dimensions. `saved_attempt.py` now requires this audit for non-diagnostic attempts and includes its result in the saved measurement. The diagnostic flag remains explicit and cannot establish delivery evidence by default. The 900-frame CPU fixture decoded all 3,600 synthetic images; negative tests reject a missing camera, a stale archive hash, rehashed changed pixels, wrong profile, and incomplete capture before a receipt can be sealed.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator/tests -v` passed 21 tests, including failed Native completion rejection. `cpu-tests.log` SHA256 `97d5a7ef295d7891d2c4fc6a10c4727bc55b167afacc1f310be92937cbf249ff`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete` passed static checks. `assignment-check.log` SHA256 `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete --require-delivery-ready` remains exit 1 because the package is partial. `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

The capture writer still needs binding to the actual C111125 map/device/detector and bicycle actor, case-specific Native world ownership and device policy adapters, runtime `process-saved`, semantic proposals, per-case offline and compatibility receipts, and canonical delivery/comparison acceptance. No synthetic image or readback is claimed as a physical recording. The source-bound media path is a tested CPU component, not a ready delivery package.

## 2026-11-23 five-case diagnostic bundle checkpoint

`build_offline_draft.py` binds all five exact straight-bicycle red-signal cases to a source-hashed plan, exact case suffix, 20-Hz/900-frame clock and four original camera profile dimensions. The inline constructions embed the source-gated signal/detector planner, synchronized Native capture, saved attempt processor, full PNG media audit and independent comparison audit. The bundled runner checks exact identity and refuses unsourced Native capture. All five pinned `runtime.py offline` checks passed with materializations under `.runtime-work/`; the 22-test focused suite and pinned preflight passed. These are diagnostic drafts, not a canonical delivery manifest or evidence of actual signal cycles.

Proof SHA-256 (logs under this assignment):

- `cpu-tests.log`: `fd8761080e71859f186d4b8bb46be0046784c9bccc0a98aa88b0581ca8e3b9a2` (exit 0)
- `cpu-preflight-bundles.log`: `0ad0074367601c50a2023e0edc39d71ee2548cc363e89fbd10bbd637c54fcdd1` (exit 0)
- `assignment-check.log`: `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035` (exit 0)
- `strict-gate.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-two_cycles_failed_detection.log`: `13b7a98d58bb7302544e11e1fe3a7275e65cd17751c7adad1c9a681748d611a8` (exit 0)
- `cpu-offline-one_cycle.log`: `9e5b0ca5bdd1245c3c962c2a8eae8fedbc180454a1c372339f5477cac3cc0d41` (exit 0)
- `cpu-offline-signal_changes.log`: `2f9652f17395fdf091b852fb4aa47d912a45d374968f176d2ca486355d2ff013` (exit 0)
- `cpu-offline-no_prior_stop.log`: `3f8eb26df53f7a5f9e737092f71137dd5e5122518c2c31e2c04728c9079d7d33` (exit 0)
- `cpu-offline-fails_to_yield.log`: `c3fef82f3e41569807eeced7b3d848263c183b1f0a0dfa0f0723381082959388` (exit 0)

Next CPU work: bind reviewed C111125 original map/device/detector and bicycle-with-rider sources to a production Native owner adapter; author canonical proposals/manifest; run exact source-shaped positive/negative compatibility, pinned process-saved and independent delivery/comparison receipts. Actual two complete cycles, detector-to-signal causality, directed-participant yield, rider visibility and statutory findings remain unverified. Scoped strict fails on truthful `partial` status.

## 2026-11-23 mandatory saved media integrity checkpoint

`saved_attempt.py` now requires the independent four-camera archive/hash/frame/pixel audit for every sealed attempt, including an explicitly diagnostic fixture. Previously a diagnostic audit failure could be ignored. The saved-attempt tests now build all four small PNG archives and prove a changed or omitted diagnostic camera source rejects processing. All five exact constructions were rebuilt to embed the corrected processor and passed pinned `runtime.py offline` at `.runtime-work/c111125-offline-<case>-v2`. The 22 focused tests passed (`cpu-tests.log` SHA256 a64f3d4c8de6d25619d4cfac987e875440304ce34178a2440a3141402e414e9e); pinned preflight passed (`cpu-preflight-bundles.log` SHA256 0fe151c01a1b8f89eee90714279ee7b2e6d06fb4c5489a06b0e0e8ea97e94afa). Offline logs and construction hashes are recorded in `result.json` and `execution-manifest.draft.json`.

This closes a saved diagnostic integrity gap, not original Native provenance. Source-backed map/device/detector and rider, canonical semantic/delivery manifest, compatibility, runtime saved processing and physical review remain incomplete.
Scoped static `assignment-check.log` exit 0 SHA256 4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035; exact scoped strict `strict-gate.log` exit 1 on truthful partial SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-24 detector occupancy through completed cycles checkpoint

`signal_trial.py` now identifies the observed first green onset through last completed red return and requires the bicycle detector zone to be occupied and its output absent throughout that window before reporting a failed detector output. Previously, one late occupied detector frame after two cross-signal rotations could satisfy the failure flag. The source-measured result now includes `detector_occupied_through_completed_cycles` and exact window frame endpoints. It still cannot establish detector-to-signal causal authority or malfunction from these observations alone.

A new negative test creates exactly that late-occupancy trace; it retains two complete cross-signal cycles but correctly reports no failed detection. All five exact diagnostic bundles were rebuilt with the corrected measurement code. The 23-test suite, pinned preflight, five exact offline cases and scoped static passed. Exact scoped strict exited 1 on truthful `partial`. Remaining CPU work includes a source-reviewed Native map/device/detector/rider packet, actual policy readback, canonical semantic proposals/manifest, compatibility/process-saved and independent delivery/comparison receipts.

SHA-256 source and proof index:

- `signal_trial.py`: `a6e791c5896873cc7ff87a013b73890e6d5ed24b1529adcc7ff8c32b8f0e229d`
- `tests/test_signal_trial.py`: `5e99867acabdd5ebd273dfb02752a935ace14847d88a9e185851c047280c57aa`
- `execution-manifest.draft.json`: `8fe21639b08de3a5c40b084a88009d31a70d33503bfa9055c1794b1da651c4d2`
- `construction-two_cycles_failed_detection.json`: `ae28fa6df1751a1abd7400798e8d147ffd487dfbfc537a9ec62a7fd97dd58097`
- `construction-one_cycle.json`: `57028975c660723a0494802610e2c5fba3de4bf9a9714c903ce0bfd4f6dcdaea`
- `construction-signal_changes.json`: `0929e07b5449ec53310e8bfddeeaa64310090c25cef15443018a8cbd39b9c8b8`
- `construction-no_prior_stop.json`: `24b6468ea2964d7cbd9509f8df48e893237188a6e476a6b8208d54ecedbabfca`
- `construction-fails_to_yield.json`: `8df709453f43543e6f348101e2f3bc3a3d34fe30b58d9d95862bc625c05c2fdf`
- `cpu-cycle-window-build.log`: `94ce843ee12d63a82e1163f9418895ef53b49e1893eb1741034e4b09918373cd`
- `cpu-cycle-window-tests.log`: `fbe12784ee06eb5b3fa3395735fbebc09aec76548b0073657350099b6be76166`
- `cpu-cycle-window-preflight.log`: `03859ffbc9b71026853ac886700245b85fe6f3c369fe22c424ceb8a42ef8b6f7`
- `cpu-cycle-window-offline-two_cycles_failed_detection.log`: `6eba6afe6488b878361ad972ba1033d6723dbc567521dd60eca421028ec5fd32`
- `cpu-cycle-window-offline-one_cycle.log`: `564f4388dad1b34d89668014e31ea3d23529aace2e16513da93d271b2b71fc02`
- `cpu-cycle-window-offline-signal_changes.log`: `73042784344daede268474d8bc0b04d80cc5b1a9d09f243dce1815d2f7782a06`
- `cpu-cycle-window-offline-no_prior_stop.log`: `7b9ba43f9c68d9d069332f2d5ce930e105c3cf6a29511511c3a272435446ef3c`
- `cpu-cycle-window-offline-fails_to_yield.log`: `8f457ef914694165adb4c34e3268bf21cb8566cf81499625eef6dbe1a1753bcb`
- `cpu-cycle-window-static.log`: `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`
- `cpu-cycle-window-strict.log`: `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`

## 2026-11-24 reciprocal site source and original readback checkpoint

`signal_trial.construct_plan` now parses the four hashed site source packets. The map must bind the exact cell, lanes and stop/entry stations. The official device and detector must name one another and the detector's zone must bind the bicycle approach lane. The bicycle blueprint packet must name the same blueprint class and an explicit rider model. Source hashes alone or a site-level `detector_controls_subject_signal` assertion do not establish these links; a rehashed detector naming another signal is rejected by a focused test. These CPU packets describe an executable source contract and are not a reviewed physical C111125 installation.

`measure_attempt` now rejects nonfinite time or bicycle motion, negative speed, nonboolean detector/participant states and unsupported original signal states, in addition to its existing sealed stream joins and two-cycle occupancy window. The 25-test focused suite passes, including the rehashed-source and resealed-original negatives. The five exact diagnostic constructions were rebuilt with the changed implementation and each passed pinned `runtime.py offline`. Pinned preflight and the exact static gate pass. `result.json` binds the current commands and SHA-256 logs, including `cpu-source-binding-strict.log`, whose exit 1 reflects truthful `partial` status.

Next: obtain a genuinely reviewed Native map, official device, detector link and bicycle-with-rider packet matching this contract; author the selected semantic proposals, measurement contracts, canonical manifest, source-shaped compatibility, saved-only and independent delivery receipts. The current five bundles remain diagnostic-only; their synthetic source packet tests do not establish the statutory detector failure or physical rider visibility. Actual two cycles, directed-participant yielding and original four-camera visibility remain GPU review checks after CPU package completion.

## 2026-11-24 owner-controlled Native execution checkpoint

`native_runner.py` now supplies a CARLA-lazy execution loop for the five exact cases. It source-checks and spawns the bicycle, requires synchronous 0.05-second world settings, issues motion requests from prior observed device/detector/cycle state, joins each post-tick row and four camera images to the exact world frame and elapsed time, and destroys its owned actor after success or failure. The caller retains world ownership and supplies reviewed adapters. A fake-world positive test seals and fully decodes all four original camera streams; a wrong-world-time negative rejects sealing and still releases the actor. The captured policy receipt remains a request/source binding, not proof of realized detector causality.

`native_capture.py` and `saved_attempt.py` now reject any non-diagnostic delivery shorter or longer than 900 observed frames. The package's five diagnostic bundles include the new runner. Twenty-eight focused tests, pinned preflight, five rebuilt exact offline cases and scoped static pass. `result.json` binds current `cpu-native-runner-*` logs and SHA-256 hashes; the exact scoped strict check remains exit 1 on truthful partial status. The next CPU deliverables are selected semantic proposals/manifest, a Native-shaped 900-frame diagnostic fixture for pinned positive/negative compatibility, runtime saved processing and independent delivery acceptance. The original C111125 site/device/detector/rider packet must be reviewed separately; no physical or legal conclusion follows from the synthetic fake-world run.

## 2026-11-24 selected 900-frame diagnostic finalization checkpoint

The selected `two_cycles_failed_detection` case now has a source-hashed diagnostic recipe under `diagnostics/` with ten original Native/site/authority packet sources, 900 timestamped trace and video-map rows, 900 Native adapter graphs and four FFV1 camera views at the required dimensions. The recipe materialized through pinned `runtime.py fixture` under `.runtime-work/`; no generated videos or temporary trees were returned under `work/`. Its source packets are synthetic diagnostic inputs and do not establish a reviewed C111125 map, official device, detector installation or rider-visible bicycle.

`analysis.py` now finalizes a 900-frame original packet/trace/video join into seven recording channels, one source context channel and a canonical Native `result.json`. The resulting selected diagnostic report passed pinned `measurement_contract.validate` and `verify_report` for all six exact requirement rows. Four target readback comparisons matched, with `physical_acceptance_claimed` and `legal_verdict_claimed` false. A separate missing `source/detector.json` fixture failed with the contract's exact expected error. The 31-test focused suite, pinned preflight, five rebuilt diagnostic offline bundles and scoped static check passed. The scoped strict gate still exits 1 on truthful `partial`.

Next CPU construction is a selected delivery manifest and semantic proposals binding this fixture and measurement contract, followed by pinned `runtime.py compatibility`, recorded-only post-capture processing and independent delivery/comparison audit receipts for all five exact cases. Keep all physical and legal judgments unresolved pending original Native evidence. `result.json` holds current scoped proof-log hashes and remains partial.

## 2026-11-24 selected pinned compatibility and saved-only checkpoint

The exact `__two_cycles_failed_detection` primary case now passes pinned `runtime.py compatibility` on a 900-frame FFV1 four-view synthetic fixture: Native recording validation, source-hashed six-row measurement verification, Core conversion, Lean decoder, rendered full video decode, and missing `source/detector.json` negative. The exact receipt is `cpu-compat-receipt-two_cycles_failed_detection.json` (SHA-256 e5887da6d1776276f618494cd8a138374a650aa5ddaca0f0587e43188cdfcc6f). The evidence scope is diagnostic software compatibility only.

The selected case also passes pinned `runtime.py process-saved` from a fresh, current-manifest materialized synthetic attempt; `cpu-saved-receipt-two_cycles_failed_detection.json` records 900 joined frames, `originals_preserved: true`, `missing_evidence: false`, and no physical or legal acceptance claim. All six constructions were rebuilt after removing an unused prohibited verdict placeholder and aligning context evidence. The 31-test focused suite and six rebuilt offline bundles pass. The provisional `execution-manifest.json` binds selected compatibility but is not delivery ready. Remaining CPU work: positive/negative compatibility for the five other exact cases, selected saved negative, production Native source binding, physical preparation, and independent delivery/comparison proof receipts. Original C111125 map/device/detector/rider causality and physical visibility remain unverified.
