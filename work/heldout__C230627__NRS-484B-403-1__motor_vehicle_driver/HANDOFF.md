# heldout__C230627__NRS-484B-403-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-403-1, cell: C230627, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/assignment.json` (50905fa419a36c03cda9118e08894a85c86c7ab9e4a30c102c73d7777c2aa140).

Exact law text: A U-turn may be made on any road where the turn can be made with safety, except as prohibited by this section [NRS-484B-403-2, NRS-484B-403-3] and by the provisions of NRS 484B.227, 484B.363 and 484B.407 [NRS-484B-227-1, NRS-484B-363-3, NRS-484B-407].

Accepted recording summaries to review: 0; inventory `inputs/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- U-turn with physical safety judgment retained
- prohibition under NRS 484B.403(2) and (3)
- prohibition under NRS 484B.227
- prohibition under NRS 484B.363
- prohibition under NRS 484B.407

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 U-turn source measurement checkpoint

The frozen evidence inventory contains zero accepted recordings. `case-plan.json` now plans seven exact cases and six comparisons for whole-maneuver clearance and each of the five cited prohibitions. These are unconstructed cases, and the cross-reference conditions remain separately sourced questions rather than asserted legal conclusions.

`u_turn_measurement.py` joins original ego and surrounding participant bodies, yaw and participant speeds at 20 Hz. It reports the first measured heading-change frame, net heading change, minimum sampled body gap over the whole recorded maneuver, and each participant's minimum sampled acceleration. Roles such as oncoming and following need an explicit source citation. `u_turn_context.json` must address all five cited prohibition IDs, keeping unknown applicability null and requiring citations for known values. A 0.5-degree yaw change locates an engineering event onset; it is not a legal U-turn or safety threshold. Legal safety and prohibition judgments remain null. Native acquisition, complete sight-distance source and actual actor braking/visibility remain to implement.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `7d74db1a129fa435559368006f751ade4ebf645660be2d198012e217ecb3a130`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `79ed4d083b416e7df6a771151586495373262830dc5f17b698c1884b57bfb69c`). They reject missing prohibition context, uncited known applicability, discontinued frames, changed actor identities, missing original motion and nonfinite participant speed. The fixture does not prove physical U-turn safety or any cited prohibition.

Next CPU work: Native U-turn geometry/controller and surrounding-user acquisition, shared sight-distance source and four cameras, saved finalizer, exact offline/positive-negative compatibility/saved-processing proofs for a primary case; then the other cases, fallback candidates, proposals and independent audits. Keep `result.json` partial until the scoped strict gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result remains partial (`strict-gate.log`).

## 2026-11-11 U-turn construction and saved-source checkpoint

`u_turn_construction.py` now selects a Native nonjunction road with opposite-direction driving lanes, builds a forward-entry/reverse-heading cubic U-turn target arc, and requests distinct oncoming/following placements. Its map selector rejects same-direction lanes and junction starts. Arc extension and participant distance are engineering controls, never legal safety thresholds. Physical road width and achieved turn remain unverified.

`u_turn_originals.py` retains original 20 Hz ego and both participant body/velocity readbacks, actor IDs and yaw, and a context packet that leaves all five cited prohibition applicability values null. `u_turn_finalizer.py` joins the original motion to trace and video frame identities, measures whole-maneuver heading/gaps/braking through `u_turn_measurement.py`, writes `u_turn_observation.jsonl`, and rejects missing trace or altered frame joins. It makes no physical or legal acceptance claim. These modules are CPU components, not a complete selected construction.

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/tests -v` passes 10 tests (`cpu-tests.log`, SHA256 `3142dc455a4cce0af445b2c1b9011146c11681877d94efcbd7628f9b54ee1448`). Scoped `worker_check --complete` passes (`worker-check.log`, SHA256 `a47f3208435860d3dbff3f50753632fc50f9082c4f3ed7bfb66d9a9314730df7`); scoped strict fails at readiness acceptance because status is correctly partial (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`).

Next: integrate the selector/recorder with a lazy Native runner, synchronized four-camera source capture and map/sign/zone/sight-distance acquisition; write root config/construction and first exact diagnostic recipe; run offline, positive and missing-source compatibility, then process-saved for `__safety_clear`. Only after that expand remaining six cases, three distinct physical-risk fallbacks each, semantic proposals, comparison/delivery audits and scoped strict. Keep unknown cited prohibition applicability null until an original source supports it.

## 2026-11-11 first Native runner draft checkpoint

`runner.py`, `u_turn_camera_capture.py` and `config.json` now compose a CARLA-lazy 160-frame/20 Hz prospective capture with four named FFV1 source cameras, PipelineCapture, FrameMap, original ego/oncoming/following motion and world restore. `construction.json` embeds the current first `__safety_clear` source and records its draft status. The safety pair has deliberately different oncoming spawn requests (24 m vs 12 m) and identical route/controller/camera plan. `case-plan.json` marks only those two drafts; five cited-prohibition cases remain planned and unconstructed. No Native physical execution or exact offline/compatibility/saved receipt is claimed.

The runner import/check is CARLA-lazy and its config identity/drift checks are included in 12 passing tests (`cpu-tests.log`, SHA256 `a308e06e11f035d7b057faacd81b8aef9c5b6580a9b58a94d9aadacf295ad972`). `runner.py --check` exits 0. Current `config.json` SHA256 `6885f8a8e799d40cee5201913ff3127c7a3f6e23df3be44443edde54f834e9a8`; `construction.json` SHA256 `d8f84bd42465c8c5c64ae5a9e042dc6b63a95ec28f40713f5229653bf44c3226`; `runner.py` SHA256 `aec4654c3dc341089d560445c2131e3601f8e6bd13c490efc559ae9fc411769c`.

Next CPU step: make the first diagnostic recipe with source-shaped original actor motion and four camera streams, build an execution manifest with exact construction hash, and run offline, positive/missing-original compatibility and process-saved for `__safety_clear`. Acquire map/device/district/divider/school-zone/sight-distance sources before selecting the five prohibition cases. Then implement three distinct risk-triggered fallbacks per selected case, semantic proposals and independent audits, rebind hashes and run scoped strict. Actual physical completion, pixel visibility and legal safety remain unverified.

Final scoped rerun after the runner/config draft: `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete` exits 0 (`worker-check.log`, SHA256 `a47f3208435860d3dbff3f50753632fc50f9082c4f3ed7bfb66d9a9314730df7`). Adding `--require-delivery-ready` exits 1 solely at readiness acceptance while status remains partial (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`).

## 2026-11-11 first exact safety-clear saved path

`__safety_clear` now has `measurement-contract-safety_clear.json`, canonical case proposal draft, source-hashed inline `construction.json`, `execution-manifest.json`, and a compact nine-frame diagnostic recipe. The diagnostic is synthetic, copied from the pinned generic Native-shaped fixture and given distinct original U-turn actor motion/context; its generated videos are black and prove software compatibility only. The finalizer keeps five cited prohibition values unknown.

Exact offline materialization passes 12 tests (`safety-clear-primary-offline-tests.log`, SHA256 `8d792d81c28f14e81434cb2a175feb8a800363e60faf05e9aa008104cb37a9c2`). Positive and deleted-`u_turn_motion.jsonl` negative compatibility pass (`safety-clear-primary-compatibility.json`, SHA256 `858bb5db76ebc4ae93ec33824bfd8957d6bc5b7eecf9837aa6d0106050f44a08`; analysis log SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; negative log SHA256 `2ecb0c0d37f9370271ad5881169b5d9b4b2ce825cb8b2572fccca184a850a75f`). Saved-only `process-saved` passes through the pinned converter/renderer/decoder with original preservation (`safety_clear-saved-proof.json`, SHA256 `c66241ae8216003d1dac66dc910fe8b6291723788334747cdffe007b13a11d4c`; processing log SHA256 `d9181a2524405ae066dcc2a7b1305412dfab139faf4abf55f4aaaa906660d34a`). Current construction SHA256 `cb527e4faa2ea1d610b815761fb4b346b595b79c228d8e87ec1a828095b4b63d`; manifest SHA256 `bc7036a1b293cb9ecd8e603c2b38b051de6eeeee44c09f6578bed4ee10964ea2`; recipe SHA256 `b443841e9dfcdaac0982beb6af32fb10c392fcfa270a73d0b80c96369a03fc39`. The source-shaped diagnostic itself is 1441842 bytes, below the return cap.

Next: exact `__safety_conflict` bundle and three risk-triggered fallbacks for both safety cases; construct original map/device/district/divider/school-zone/sight-distance sources for the five cited-prohibition cases; complete their exact proofs and independent audits; canonical semantic stages; scoped strict. Do not infer a safe-turn threshold from 24 m versus 12 m engineering spawn requests.

Current scoped `worker_check --complete` passes (`worker-check.log`, SHA256 `a47f3208435860d3dbff3f50753632fc50f9082c4f3ed7bfb66d9a9314730df7`). Scoped `--complete --require-delivery-ready` fails at readiness acceptance while status is partial (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). This is a first-case checkpoint, not assignment readiness.

## Subsequent safety-pair expansion (proof rebind pending)

`__safety_conflict` now has an exact inline construction, measurement contract, case proposal and diagnostic with the oncoming actor 8 m closer than `__safety_clear`, with fixed route/controller/cameras. `audit_safety_comparison.py` checks both constructions, all unchanged diagnostic sources and the sole original actor-position difference; two negative-control tests reject camera and following-speed drift. Fourteen package tests pass (`cpu-tests.log`, SHA256 `e1641566b2bb308066ca4d3d4a78bf75699ec229a8108b255aa446eb8ca5ce58`), and the independent audit command exits 0 (`safety-comparison-audit.log`, SHA256 `dbac6c5bfeff5ffdadd7cd6f89a3618ce2ceb153951c866709adeada163667ec`).

Three distinct fallback constructions for each safety case are static-validated by the pinned candidate selector: finer waypoint sampling for route discovery, shorter arc extension for road envelope risk, and farther following spawn for actor overlap risk. They preserve the deliberate oncoming-distance comparison. Runner/test source changed and all eight inline constructions were rebound. The earlier `__safety_clear` exact receipts and saved proof refer to the previous construction; they are historical, and current manifest proof fields were removed pending rerun. No new fixture was launched during the lead's full-gate window.

## 2026-11-11 exact two-case safety matrix rebound

The first two safety cases now have eight current inline constructions (primary plus three physical-risk fallbacks per case), all eight exact offline proofs and all eight positive/deleted-`u_turn_motion.jsonl` negative compatibility receipts. Pinned `candidate_constructions.validate(required=True, candidate_count=4)` passes both cases; `package_compatibility.check_receipts` passes. Saved-only `process-saved` passes for both primaries with current manifest/construction hashes. The independent safety comparison audit passes and rejects camera/other-participant drift. Delivery source audit passes on both four-camera diagnostic streams and rejects a tampered original motion hash. All synthetic media remain software-only.

| Case | Primary construction SHA256 | Primary compatibility receipt SHA256 | Saved proof SHA256 |
|---|---|---|---|
| `__safety_clear` | `080c65d74dca1a3715d03da7fce028d9f7a6257211b4c9b8c00f28a8e6c63cd2` | `ba04bb3027827e6731a774d2cec8274347003ea0d93b2bc3cea51c7b1ca7b0b1` | `467aa5d4e4809f1a565f47cec590796e9f3b82b8604f1bc9ccd7927dc15a81c9` |
| `__safety_conflict` | `43120acb2f5a1059aac7b3671490dbe305ddc1b23886a5c2ecb1c69bfa02009d` | `e93036bd5fdb91b1a674d6fa46523014507158f24d609e58055d6fde278e749e` | `1478a4212c2bfdda9e5e9f3281f79bf7506ee4334ab6de149c5d01fbf8d89460` |

Each fallback construction/trigger and exact proof is individually bound in `execution-manifest.json` (SHA256 `1397771c01844c27b1bee40d242aa63de5ae7ca6d4daff5ac952cad6adf3b9b6`). Main 14-test CPU suite SHA256 `0fcc7174efa7ac52ea6e6ba53ae59c1d3df20c5b64776f1017db14caf4e1a0b3`; comparison audit log SHA256 `dbac6c5bfeff5ffdadd7cd6f89a3618ce2ceb153951c866709adeada163667ec`. Independent delivery positive/negative logs are bound in each manifest case.

Remaining CPU work: construct/map-source the five cited prohibition feature cases and controlled comparisons, prove each exact case and three distinct physical-risk fallbacks, complete seven canonical semantic stages and their independent audits, then rerun scoped strict. There is no legal safety cutoff inferred from the 24 m/12 m engineering spawn requests; no actual U-turn or pixel visibility is claimed.

Scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete` exits 0 (`worker-check.log`, SHA256 `a47f3208435860d3dbff3f50753632fc50f9082c4f3ed7bfb66d9a9314730df7`). Scoped strict with `--require-delivery-ready` exits 1 at preparation acceptance because the result remains truthful partial (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`).
