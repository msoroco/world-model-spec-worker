# NRS-484B-769 at C229831

Actor: `cycle_or_scooter_operator`. Frozen cell: `road` / `right_turn` / `intersection_boundary`.

Witness branch: general_method_right_turn_signal.

Comparison variable: `cycle_right_turn_hand_signal`. Three planned physical probes use horizontal right arm, no requested hand signal, and upward left arm on the same authored right-turn route. These are requested physical conditions, not observed behavior or legal verdicts.

Source: `inputs/training__C229831__NRS-484B-769__cycle_or_scooter_operator/assignment.json`, SHA-256 `915f0f5b2b0e44747d960300a1e409d838284629ebded01196cfda52817954e9`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: three planned probes have an authored road, bicycle controller, rider arm rig, source join, saved-only diagnostic, and prospective Native runner; exact selected materialized bundles, offline and compatibility proofs, semantic proposals and independent audits remain unfinished. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 source-bound arm geometry checkpoint

The frozen law governs bicycle, electric-bicycle and electric-scooter operators on a roadway. The planned pair keeps one bicycle, operator, connected right turn, and four-camera 30-second capture fixed; only the requested arm pose differs. The horizontal-right exception is explicit in NRS 484B.769. The general method is referenced as NRS 484B.420 [DEF-NRS-484B-420] and was separately reviewed on the Nevada Legislature website; no general-method verdict is asserted.

`native/measure_hand_signal.py` joins 600 raw 20-Hz samples to sourced rider identity, machine class, roadway polygon, route and calibrated shoulder/elbow/wrist keypoints. The proof has an extended-arm positive run (frames 100–139), no-extension comparison, and six rejections for missing keypoints, bad time join, wrong rider, missing roadway source, wrong machine class, and a derived-only hand-signal channel. The geometry tolerances are engineering diagnostics. No frame is asserted to be real Native capture.

Pinned runtime preflight passed. `.venv-cpu/bin/python worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete` passed static checkpoint. Source and proof hashes:

- `native/measure_hand_signal.py` SHA-256 `37003dc7be20a39edff254d5c4880680ebd99dee418ff4256ce3d43d9f6ce7de`
- `native/prove_hand_signal.py` SHA-256 `1144ef9059f4d358d7421b1ce985a36fe9875da4e3adb419356fdd61376462ce`
- `native/measurement-contract.json` SHA-256 `16b8d19100b7ef9d9de88057a41a1eb2f800c6f8a7142e15949a295635f49d4c`
- `native/route-and-arm-proposal.json` SHA-256 `2ef83ce177dabc4a3a0b6349fd69551b2a77348ed43a10753d0eaf901b67c24e`
- `native/hand-signal-proof.log` SHA-256 `c42f37cd76bacd467a523a2295ad09869e58b8131a8fd422899e633c39b9e969`

The pinned adapter removes `sig.hand_signal`, so the source acquisition and saved finalizer must be implemented and tested before a selected case can be declared. Native articulated arm control, exact offline and compatibility proofs, process-saved, candidates, and independent acceptance/comparison audits remain CPU work. Physical arm visibility and actual motion remain unverified. Status is partial.

## 2026-11-27 referenced method and Native rider rig checkpoint

Nevada Legislature NRS 484B.420, reviewed at https://www.leg.state.nv.us/nrs/NRS-484B.html, specifies a left-arm upward right-turn method; the frozen NRS 484B.769 text permits the horizontal-right-arm alternative. `native/source-review.json` records the authority and scope limits. No advance-signal duration or obligation to signal every right turn is inferred from NRS 484B.769. The planned controlled set now includes `__probe_a` horizontal right arm, `__probe_b` no requested arm signal, and `__probe_c` upward left arm; both methods still require original capture and independent pixel review.

`native/rider_arm.py` spawns a distinct walker rider with the selected bicycle and requests either articulated pose or neutral pose each frame. It requires original shoulder/forearm/hand world-position readback for both arms and records requested bones separately from observed geometry. The mount is a prospective acquisition rig: original pixels must prove actual mounted appearance and visibility. `native/source_rows.py` derives roadway occupancy and route proximity from sourced polygon and route geometry, joins 600 original rider/camera frames, and feeds the existing right-arm diagnostic. `native/measure_general_signal.py` measures a separately sourced 3D left-arm upward diagnostic. Numeric pose margins are engineering diagnostics, not legal thresholds.

CPU commands: `.venv-cpu/bin/python -m unittest discover -s work/training__C229831__NRS-484B-769__cycle_or_scooter_operator/native -p test_*.py` (9 tests, exit 0); `.venv-cpu/bin/python native/prove_hand_signal.py` from the native directory (positive and six negative proofs, exit 0); `.venv-cpu/bin/python worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete` (exit 0). Logs and file hashes:

- `native/rider_arm.py` SHA-256 `1da08d8536d03b124e31bec2a5a417513ed29ecc627153c8380d7fe2e95b8271`
- `native/test_rider_arm.py` SHA-256 `4b7337de1ba0f0cf183c90c15a07320eae891f417db7cb933b27dd9d3b07fd2e`
- `native/measure_general_signal.py` SHA-256 `111040cbfb1e276b2029e5d4f5c473cb30b189713948293f8e468ec38b99cc99`
- `native/test_general_signal.py` SHA-256 `3b38ce659445491c30cc76c33462df5e85fa9790ff1b69ff46daea8506c054f4`
- `native/source_rows.py` SHA-256 `f3ae6683e422342979063fbe15844eadc30dd09bb27ec1b64e99f485069619b9`
- `native/test_source_rows.py` SHA-256 `2d130b84dd3ab89a6c6576d8a4fdd22baba2b0f0d93c97f0a4a1f086ce88175f`
- `native/source-review.json` SHA-256 `9474e97876dc4d869a55b956cdf4a360655975b6c4aa609351f166709369bc4a`
- `native/native-rig-tests.log` SHA-256 `25660486d75d5f4b9efa5b4fdd11e9e694dfc634802c6601b239be93e2d13722`
- `native/current-static-check.log` SHA-256 `3c14b423fd384815c06456aac648c724f01e38253818fe7b7a623f138cc03929`
- `case-plan.json` SHA-256 `243aa19f426bb2f6e4dfe2d4588495723907196f91d08e0b20fe1c42fdf2a230`
- `result.json` SHA-256 `3cb93928aac92616b4cf991d24e44b8092f79aa8ed0c49021817bda087db4536`

Remaining CPU work: author exact 600-frame CARLA route and four-camera capture runner, seal original source/readback and map context, saved-only finalizer, source-bound positive and missing-source compatibility fixtures, exact offline receipts, canonical semantic proposals, independent delivery/comparison audits, and strict assignment gate. Physical bike/rider mounting, arm pose, camera visibility and actual turn remain unverified. Status remains partial.

## 2026-11-27 prospective capture and saved finalizer checkpoint

`native/road.py` authors a three-road connected OpenDRIVE right-turn junction and lane-center path. `native/route_control.py` uses original bicycle pose readback to steer `vehicle.bh.crossbike` through the junction. `native/rider_arm.py` separates pre-tick arm requests from post-tick original world-bone and full bicycle-body readback. `native/runner.py` authors a prospective 600-frame, 20-Hz, four-camera Native capture with map lane readback, synchronized frame map, pipeline capture, original arm/road sources, lossless camera streams, world restoration and sealing. Its `--check` passed for all three exact probe IDs; no CARLA server was run here.

`native/finalize_sources.py` joins three hashed sealed sources (`rider_arm.jsonl`, `camera_frames.jsonl`, `road_context.json`) to derive right-horizontal and left-upward arm diagnostics. It rejects a stale seal, missing camera source, and fixture presented as original. Source rows require all original full bicycle vertices inside the roadway polygon and derive route proximity from geometry. A fixture can test logic only; finalizer output keeps original pixels, rider mounting and legal findings unresolved.

Focused CPU proof: `.venv-cpu/bin/python -m unittest discover -s work/training__C229831__NRS-484B-769__cycle_or_scooter_operator/native -p test_*.py` passed 18 tests. All three `native/runner.py --check --case` commands passed. Static `.venv-cpu/bin/python worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete` passed before final checkpoint refresh; rerun after result update.

Current files and SHA-256:

- `native/finalize_sources.py` `bb9002b90c9b70d7bfd34c6d15ab9e467bba1168daa5ea8d1cbf74870275ee85`
- `native/measure_general_signal.py` `111040cbfb1e276b2029e5d4f5c473cb30b189713948293f8e468ec38b99cc99`
- `native/measure_hand_signal.py` `37003dc7be20a39edff254d5c4880680ebd99dee418ff4256ce3d43d9f6ce7de`
- `native/prove_hand_signal.py` `1144ef9059f4d358d7421b1ce985a36fe9875da4e3adb419356fdd61376462ce`
- `native/rider_arm.py` `455102409ae5ac15da47699fe3955b6f452420a354db69e25369833b23fbfa01`
- `native/road.py` `64e33fde0afd2e1b9892416bef488f2617517dbaa03beddc05c529049f326694`
- `native/route_control.py` `ec63ed833e0b1f1101f2bd79185895726e6bee30feb44d39c0761c68b6c15f19`
- `native/runner.py` `49cf4d5c81f30d33bf0d777dccb9df4053fd84c2ad12dae6341e57ed58aa6d47`
- `native/source_rows.py` `414fe3d9959df98a8e2fe0a047416acddb48580ba248688ae354d49c653ad6b9`
- `native/test_finalize_sources.py` `0d80630558ed168e75706debbc93f715736666f74e84f9f3e2b2a0b6d0e8d12b`
- `native/test_general_signal.py` `3b38ce659445491c30cc76c33462df5e85fa9790ff1b69ff46daea8506c054f4`
- `native/test_rider_arm.py` `81e8727b53ebf2340104674be5754c8d578fa7af1840f319cc48ea99b9c57c65`
- `native/test_road.py` `14cee6a9d3772230183ae0afc7b3510ac67bd83aa9c6df345744e3c759acd520`
- `native/test_route_control.py` `397cf5e20e2c7fd100c015f4ade426ef251cbc4d61e177c20fc74636666f0bd5`
- `native/test_runner.py` `7f3b9eafdb3f66388fefc8bee08571311956681a2b9dbb0c3ca97a59dbb66e79`
- `native/test_source_rows.py` `f4b3bbf73c8b43a2e562f86d3619d81dff97635d05a5c5d66dccc28bdc35b3ba`
- `native/measurement-contract.json` `8e75dee0f2d2844f5ad1beb8c2363882e947ea8902e291529c137610b52d049d`
- `native/route-and-arm-proposal.json` `52af8b79c4931d6f67134aa036346525c80faae802ae421391d7ed308547e7ee`
- `native/source-review.json` `9474e97876dc4d869a55b956cdf4a360655975b6c4aa609351f166709369bc4a`
- `native/runner-check-a.log` `59cfa3382b3d720c62fd5d507baee19d7c6ebe3fb9077f3376cf24ee1e66c931`
- `native/runner-check-b.log` `7fbd3227f46a419abceb20c3128bef4f3eeb5ae9ec376561601e9a2ca421d254`
- `native/runner-check-c.log` `d75403b7b4dfcc2c3a6dc9376539f81d86dba2de9c1ccc1981dd2e3478893491`
- `native/native-tests.log` `e185de29b69e51909b3c6d726a6dcdf7459c6453b01611a1245082f4cd16302e`
- `case-plan.json` `8dfa78f033c96459d54f624e18282c58f2c9fcc56b4f35427a6f2bc7c3936064`
- `result.json` `15899a5989ea2ce2a72b91233cfa8a8cd13909ec67e08ccfa1da3407eb72ca32`

Next CPU actions: bind these sources to exact materialized selected-case constructions and canonical saved `write_result`; run runtime offline/positive and missing-source compatibility for each case and justified physical fallback; author stage proposals plus independent delivery and comparison audits; then run the exact strict assignment gate. No package readiness claim is made.

## 2026-11-27 exact selected CPU proof checkpoint

Three selected 600-frame Native construction bundles and one physical fallback each are authored in `execution-manifest.json` and `native/selected-drafts/`. `runtime.py offline` passed for all six selected candidates. Public `runtime.py compatibility` passed six positive source-bound diagnostics and six missing `rider_arm.jsonl` negative diagnostics. Each compatibility receipt and log is bound under `proofs/{a,b,c}/{primary,fallback1}/`. Compatibility materializes a synthetic saved-source fixture, decodes four streams, joins original-looking arm and roadway rows, and measures 40 right-arm frames for probe a, zero signal frames for b, and 40 upward left-arm frames for c. It does not prove an actual Native capture.

`native/prove_physical.py` exercised `worker_exchange.native_output.physical_result` for complete, incomplete and missing motion in all three cases; nine results/logs are bound under `proofs/{a,b,c}/physical/` through `physical_preparation`. These are declared synthetic fixtures and make no physical or legal acceptance claim. `native/finalize_sources.py` now checks capture seal and every original stream hash. `finalize.py` is a canonical saved-only finalizer and the focused Native suite passed 22 tests. Scoped `worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete` passed.

Remaining: full canonical semantic stage proposals, independent delivery and comparison acceptance scripts/receipts, saved processing and case-plan source mappings, then exact strict scoped check. Original CARLA pixels, mounted rider arm and completed real turn remain unverified. Status partial.

## 2026-11-27 strict delivery-preparation acceptance

The exact scoped strict gate passed: `.venv-cpu/bin/python worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete --require-delivery-ready` (exit 0, `static_checks_passed: true`). The final package contains three selected cases and one physical fallback per case; six exact offline proofs, six public compatibility positive and missing-arm-source rejection receipts, nine source-bound synthetic physical outcomes, and three recorded-only saved-processing receipts. All three selected cases have independent 600-frame/four-video delivery audits and negative missing-source tests; the two controlled arm-method comparisons have independent saved-source audits. The five-stage draft semantic proposal chain validated against pinned contracts. Top-level delivery tests passed 3 tests and the focused Native suite passed 22 tests.

Readiness means CPU delivery preparation passed. Original CARLA pixels, mounted rider appearance, actual arm visibility and physical right-turn completion require Native execution and independent review. No legal verdict is claimed.
