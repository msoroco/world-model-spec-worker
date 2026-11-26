# NRS-484B-270-2a at C247014

Actor: `motor_vehicle_driver`. Frozen cell: `same_direction_multilane` / `overtake` / `cyclist`.

Exact statutory source: NRS 484B.270(2)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Due care and conditional immediate-left-lane movement. Planned comparison variable: `immediate_left_lane_for_cycle_pass`. Requests: driver changes to available immediate left lane before cyclist pass; driver passes cyclist without moving into available immediate left lane. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject overtakes or passes a bicycle, electric bicycle or electric scooter going the same way; there is more than one lane for traffic in that direction; the lane to the immediate left is available.

Timing to retain: the lane change precedes the abreast phase — the subject must already be in the left lane when it passes; the left lane is held for the whole of the pass.

Exceptions and numeric alternatives planned: the lane to the immediate left is not available, or moving into it would not be reasonably safe.

Unresolved judgment or rule composition: 'due care' and 'reasonably safe' are judgement elements needing declared bounds. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU same-direction bicycle-pass source diagnostic

Added `native/cycle_pass_measure.py` and `native/prove_cycle_pass_measure.py`. The saved-source diagnostic requires a covered bicycle, electric bicycle or electric scooter; at least two same-direction lanes; distinct subject and immediate-left lane IDs; full 600-frame, 20 Hz same-direction actor histories; and four pinned camera identities. It measures the body-overlap passing span and counts subject frames in the immediate-left lane, including when that lane was first entered. Left-lane availability and reasonable safety remain source declarations needing original evidence; due care is not judged.

Four planned synthetic case shapes keep the longitudinal bicycle pass fixed at frames 320 through 480. The lane-change witness enters the immediate-left lane at frame 300, before passing, and stays there through the pass. The no-change witness and exception-absent comparator remain in the right lane; the exception-present shape declares the left lane unavailable. A fifth diagnostic exercises the alternative that moving left would not be reasonably safe, without claiming a new selected case. Six missing-source mutations reject wrong machine type, one-lane roadway, missing availability, truncated history, camera loss and opposing direction. These are `synthetic_native_sample` traces, not Native observations or legal acceptance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_cycle_pass_measure.py > native/cycle-pass-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C247014__NRS-484B-270-2a__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `358a532f07479557fa65f8572695379b2e0bc71070a13909103edbc6dbfeb0ce`; proof script `fc325c6a0557e66661e27c75e08c96e9782842e878693c3304b4d6dce7f0247c`; proof result `3c27ce88496480666cade1dab183cf7afbb36abc51281f30a71f0a90e65216af`; preflight log `d546e6a47654da70b2bef89b1f480f704459d050e515a3f2372fb7947428b431`; scoped checkpoint log `0c03e118d73f22a45253a0657526a0a4ff41fb4c51a1e7b2320878c09b4270f5`.

Next CPU work: implement exact multilane Native scene and both lane controllers with source-based lane availability and safety diagnostics, four source camera videos, execution manifest, pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. Make the linked comparison hold the bicycle path fixed and prove lane change before the full pass. No exact construction bundle exists yet; keep `result.json` partial.

## 2026-11-26 four-case Native construction draft

`native/scene.py` authors a 400 m, two same-direction lane OpenDRIVE road and an exact 600-frame plan for all four case suffixes. The immediate-left lane is -1; the subject starts in -2. The witness_1 target completes its lane change by frame 260 before the expected body-overlap pass (frames 280 to 386), while witness_2 and exception_1_1 remain in the right lane. Exception_1_2 adds an original Native left-lane occupant to provide a measurable availability contrast. These are construction targets; original actor readback must verify realized motion and lane occupancy. No legal safety or due-care judgment is encoded.

`native/runner.py` provides lazy `--check` for each exact suffix and a prospective original CARLA capture with ego/cyclist/blocker actors, source pose rows, four 20 Hz camera encoders, a frame map, authored road readback, world restoration and capture sealing. It has not run on a Native host. `native/test_scene.py` passed four focused geometry/order/identity tests in `native/scene-tests.log` (SHA-256 1c23f3e4bb2dec8b573732fcfbd8ab2dd9a3d152e1fdf2ae4fccbbee49cd444a). Runner SHA-256 3e836605ab1fb4b9558ef79e11960406eb4d6e620b0393e9b138c743d86d8980; scene SHA-256 e35c7470678400c7dd1f6e38c62887ede0e0538e6e21a30cd5087a29a549751f. The selected diagnostic proof remains unchanged. Next: materialize exact inline bundles and source-bound saved finalizer, run pinned offline and public positive/missing-source negatives for each case, then recorded-only, semantic, physical and independent audits. Keep result partial until the exact strict scoped gate passes.

## 2026-11-26 exact Native offline milestone

`build-native-draft.py` materialized four exact inline constructions under `selected-native-draft/` with the same source-hashed runner, road plan, four cameras, 20 Hz and 30-second contract. `selected-native-draft-manifest.json` binds each distinct case ID and construction hash. All four current-runtime `runtime.py offline` commands passed in fresh `.runtime-work/` outputs; `bind-native-offline.py` checked their exact case/candidate identities and bound retained logs. Manifest SHA-256 b6eff456cb860df00852e983653dfaa91ca46e45fd5a41a833dd29782a83f1a7. The inline bundles are CPU drafts: they have not run on a Native host and the saved finalizer, public compatibility, recorded-only processing, semantic and independent audits remain to be completed. Original immediate-left occupancy, reasonably safe movement and due care are not claimed.

The Native controller sign was corrected after reviewing CARLA steering direction: negative steering requests a leftward (+y) move from the right lane. The CPU suite now passes five tests including leftward/rightward and yaw-correction signs. All four exact offline bundles were regenerated and rerun against this corrected runner in fresh `.runtime-work/c247014-offline-v2-*` outputs; all passed. Current selected Native draft manifest SHA-256 b5fafa67b1c0f41df5c2af2ede48b8dfd8b46a4eeda2620222a0e1ce7263109e; current runner SHA-256 548d39626ef9412a36104ff740291c4a136c7d4417b1ae7d9a00c30435ee6843; current test log SHA-256 45533230f0145ede10e2c72c5e5e58a3786aa370551cd293cac56258aa45e7fa. No original vehicle motion is inferred from these checks.

## 2026-11-26 source-joined saved finalizer draft

`native/finalize.py` now checks the authored original road lane identities and joins 600 participant-pose, trace, camera-map and capture-evidence rows before measuring left-lane occupancy through the body-overlap pass. It records original source hashes and explicitly leaves lane availability, reasonable safety, due care, physical completion and legal conclusion unaccepted. The source-shaped diagnostic fixture tests positive joins and a missing-road negative; all six Native tests pass in `native/native-tests.log` (SHA-256 379b6712fa680286d15a680ec72476df691263462dcc86c26360bae50f5ae5cf). This fixture is not an original Native recording. All four exact inline bundles now include that finalizer and test and pass pinned offline; current draft manifest SHA-256 e2907b23254e752f95888f68620afca1aea0bddcc7d2975089ec4f62964b97b0. The saved processor has not yet been exercised end to end: canonical channel evidence, public positive/missing-source compatibility, semantic, physical and independent audits remain CPU work. Keep partial.

The saved finalizer now also writes six frame-joined measured channel files and one explicit unresolved availability context file; it leaves all acceptance flags false. A diagnostic 600-frame fixture exercised that saved writer and its missing-road negative. Seven Native CPU tests pass (`native/native-tests.log` SHA-256 67ee230c5d1365b13dbdbed51f3620a45fd9e7a29a88b2801a5785ebaabd4db1). All four exact inline bundles were regenerated and passed pinned offline again in fresh `.runtime-work/c247014-offline-v4-*`; current draft manifest SHA-256 1d508ec3dc2766328847a59fd5d2e2add8435180e292610ace2513c1e8eb1509. This is still a CPU source-shaped proof, not full public compatibility or recorded-only `process-saved` acceptance.

The saved finalizer now writes six measured channels and explicit unresolved left-lane availability context. A second source-shaped fixture test verifies seven recording-evidence references, 600 rows and unaccepted status. Seven Native CPU tests pass (`native/native-tests.log` SHA-256 67ee230c5d1365b13dbdbed51f3620a45fd9e7a29a88b2801a5785ebaabd4db1). All four exact inline bundles regenerated and passed current-runtime offline in `.runtime-work/c247014-offline-v4-*`; manifest SHA-256 1d508ec3dc2766328847a59fd5d2e2add8435180e292610ace2513c1e8eb1509. Next CPU action is a measurement contract plus case-specific public diagnostic recipe for positive/missing-source compatibility, then recorded-only `process-saved`. Original physical and legal outcomes remain unverified.

## 2026-11-26 current-runtime rebinding and saved proof

The exact `config.case.recording_description` source field was missing in the first rebuilt drafts. The local builder now copies the construction recording contract into that case field. All four rebuilt exact case constructions passed current-runtime `runtime.py offline` in fresh `.runtime-work/c247014-offline-v8-*` outputs and public/Core compatibility positive plus missing-context negatives in `.runtime-work/c247014-compat-*-v4`. `selected-native-draft-manifest.json` SHA-256: `fed6541c1b01bff9f1c4da4618565c03f9e253781be92d4698e2bfbf0b6b4652`.

All four exact cases passed recorded-only `runtime.py process-saved` from source-shaped fixture artifacts. Each joined 600 frames, retained source originals and made no physical or legal acceptance claim. Removing `pass-context.json` in a separate witness_1 run produced `missing_evidence=true`, explicit incomplete/unavailable-law-evidence feedback and preserved originals. The bound `native/recorded-only-proof.json` SHA-256 is `1a3c6f0d9979eb55ff3c595973b26722b6a7319951afe0b4a1faede08226fc4a`. These CPU fixtures do not establish original Native behavior.

The seven-stage draft semantic proposal chain now validates against the exact law, four selected constructions and source-bound recording description. Its index SHA-256 is `b347c3dc132643884b0d15de9b7336852e4e7b6335cfd7fa20f4dd96de3ad717`. The two judgment phrases remain unresolved; the physical sweep is explicitly incomplete because feasible source-grounded ranges and original Native readback are missing. This semantic pass is a structural CPU check, not a legal finding.

Next: build and prove measurable physical fallbacks for each selected case; add the reasonably-unsafe-while-available branch independently of unavailable-left-lane occupancy; complete source observation mappings, exact four-view camera plan, physical/lifecycle and independent delivery/comparison audits; bind canonical root execution files and run the scoped strict delivery gate. Keep `result.json` partial until that command passes. No original CARLA motion or legal outcome is claimed.

## 2026-11-26 measured-trigger Native fallback milestone

`build-fallback.py` authored `fallback1` for all four exact case IDs, preserving each case, actor, four cameras and recording description. It changes only physical control targets: ego longitudinal target from 3.0 to 2.8 m/s and the planned left transition from frames 180–260 to 140–240. Its trigger is an original saved participant-pose and left-lane-occupancy failure to realize the planned pre-pass and throughout-pass lane occupancy or the original passing motion. All four fallback constructions passed exact current-runtime `runtime.py offline`, public/Core positive plus missing-context compatibility, and `candidate_constructions.validate(required=True, require_alternate=True)`. Manifest SHA-256 after binding is `43c0df681d71cbefec654a7255e633a402779e7e80f3ad43d47e4b39993c22be`.

These are CPU-tested alternatives, not original Native realizations. The selected semantic judgment sweep is explicitly incomplete. Physical/lifecycle and independent delivery/comparison audits, root execution package and strict scoped gate remain. `result.json` stays partial.
