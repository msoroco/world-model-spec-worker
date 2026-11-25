# testing__C111610__NRS-484B-283-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(a); with 484B.283(4) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: When official traffic-control devices are not in place or not in operation, the driver of a vehicle shall yield the right-of-way, slowing down or stopping if need be so to yield, to a pedestrian crossing the highway within a crosswalk when the pedestrian is upon the half of the highway upon which the vehicle is traveling or onto which the vehicle is turning, or when the pedestrian is approaching so closely from the opposite half of the highway as to be in danger. As used in this section, “half of the highway” means all traffic lanes of a highway which are designated for traffic traveling in one direction, and includes the entire highway in the case of a one-way highway.
Assigned branch(es): Pedestrian on the half onto which ego turns..
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

- `case-plan.json` now lists seven exact cases and five controlled comparisons for the fixed left turn. It separates destination-half occupancy, complete device absence versus nonoperation/operation, opposite-half proximity requiring independent danger review, and source-classified crosswalk placement. This is a plan, not accepted coverage. The introductory NRS 484B.287, 484B.290 and 484B.350 exceptions remain explicitly source-reviewed rather than inferred. There is no frozen accepted recording or exact-law judgment range.
- `crosswalk.py` verifies original map/site and all destination-direction driving lanes, complete relevant official-device inventory, source classifications, separate participant identities, original frame joins and geometric projection. `native_setup.py` checks connected original lane waypoints, spawns separate CARLA actors lazily with cleanup and applies a source-gated engineering hold policy. `scenes/*.json` are seven nominal specifications awaiting original map binding; their coordinates are not asserted physical facts.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-283-1a__motor_vehicle_driver/tests -v` passed 9 tests; output is `cpu-tests.log`, with SHA256 recorded in `result.json`. Positive and negative tests exercise source rejection, full directional-half lane inventory, frame join, spawn cleanup, participant position, fixed comparison conditions and device gating.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete` passed static checks (`check-complete.log`). The same command with `--require-delivery-ready` failed at `Preparation acceptance failed: partial/missing packages remain` (`check-strict.log`), correctly reflecting partial status.
- Next CPU work: bind an original map/site survey to every scene, implement full 20 Hz Native capture and four-camera frame map, source-sealed saved finalizer, semantic proposals, execution manifest, per-case offline and source-bound positive/negative compatibility checks, saved processing, independent delivery audit and comparison receipts. Re-run exact strict gate. Physical CARLA realization and pixel visibility follow CPU preparation.

## 2026-11-24 saved measurement checkpoint

- `saved_measurement.py` binds a case-specific scene SHA, sealed original site/ego/pedestrian/exception files, original map identity, complete 600-frame 20 Hz sequences, stable separate actor IDs, source-classified crosswalk and directional half, complete relevant device inventory/state, and per-frame geometry/brake outputs. It emits source hashes and measured summaries with legal judgment and physical/pixel verification explicitly unresolved. It is a saved-only processor for all seven scene specifications; it is not proof that the source-index provenance assertion came from CARLA.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-283-1a__motor_vehicle_driver/tests -v` passed 15 tests (`cpu-tests.log`, SHA256 in `result.json`); six new tests include a 600-frame positive source join and rejection of tampering, missing source, frame-time drift, actor drift, scene/provenance drift, path escape and unverified device history.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete` passed (`check-complete.log`); exact `--require-delivery-ready` exited 1 on partial status (`check-strict.log`).
- Next CPU actions: acquire and seal the original site/map packet with the actual Native runner; capture 600 source-bound frames and synchronized four-camera frame identities for each selected case; add finalizer, semantic proposals, execution manifest, per-case offline and positive/negative compatibility proofs, saved processing and independent delivery/comparison audits. Rerun exact scoped strict check. Physical motion and pixel outcomes remain later GPU checks.

## 2026-11-24 saved comparison audit checkpoint

- `saved_comparison.py` independently reopens and hashes two sealed attempts through `saved_measurement.process`, requires the exact declared pair and order, verifies the common 600-frame camera/duration plan, original site/crosswalk/turn geometry, identical ego control/motion and exception source/status, and checks a measured difference for all five declared comparison variable kinds. Device pairs permit only the original device inventory to differ. It does not assert physical source provenance, visibility, danger or a legal verdict.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-283-1a__motor_vehicle_driver/tests -v` passed 20 tests (`cpu-tests.log`; SHA256 in `result.json`). New tests cover positive destination-half and device contrasts, changed fixed site and ego, reused attempt, absent measured difference and tampered source.
- Exact assignment `worker_check.py --complete` passed (`check-complete.log`). Exact `--require-delivery-ready` exited 1 on `partial/missing packages remain` (`check-strict.log`); status remains partial.
- Remaining CPU work: original Native map/site acquisition, synchronized four-camera 20 Hz capture and frame map, semantic proposals, execution manifest, per-case offline and positive/negative compatibility receipts, saved delivery processing, independent delivery audit and exact-case receipts. Then rerun exact strict gate.

## 2026-11-24 exact observed-case checkpoint

`saved_measurement.check_planned_observation` now requires source-measured, 20-consecutive-frame region evidence in the middle 20 seconds of the 30-second attempt. It separates destination-half crosswalk occupancy, opposite-half crosswalk occupancy, outside-crosswalk placement and a clear destination-half case. It rejects a planned official-device condition that differs from the sealed original inventory/state. The 20-frame duration is an engineering stability witness, not a legal definition of proximity or danger. The independent comparison replays these stronger exact-case checks before comparing deliberate differences. The focused 23-test suite passed (`cpu-tests.log`, SHA-256 `10a431c1ce72290133ba5b1903c2a9eece69c497afee90b7f7451914436eaf75`). Actual map/site, Native capture, exact offline/compatibility proofs, semantic stages, saved delivery and physical visibility remain unfinished.

## 2026-11-23 original-frame acquisition writer checkpoint

`native_capture.py` now seals one exact 600-tick, 20 Hz attempt from a supplied Native adapter. It checks the source-hashed site attestation, complete directional-half/map packet and independent exception-review source; preserves original CARLA frame/time alongside the episode index; requires stable ego/pedestrian IDs and classifications; fully parses four RGB/RGBA PNGs per tick at the pinned production dimensions; and writes a SHA-bound source index, frame map and camera manifest. It refuses a nonempty attempt directory. The adapter still owns world lease, actor controls and cleanup.

A 600-frame fake adapter exercised the writer and fed its output directly to the existing `saved_measurement.process`; frame-gap, camera-omission, site-attestation tamper and nonempty-attempt tests reject. This proves software joins only. The test uses explicitly small camera dimensions and writes all generated media under `.runtime-work/`; no fake image is offered as physical evidence. The focused suite passes 26 tests. Pinned preflight and assignment static `--complete` pass; exact scoped strict exits 1 on truthful partial status. Exact commands and log hashes are in `result.json`.

Next CPU work: bind an original site/map survey and a real CARLA adapter to this writer; independently audit every saved camera source and physical pixel/completion evidence; author seven inline constructions, execution manifest, semantic stages, diagnostic recipes and finalizers, then run pinned offline, positive/negative compatibility and saved-only delivery proofs. No execution manifest exists yet, so pinned offline cannot run for this assignment at this checkpoint. The original CARLA and legal outcomes remain unverified.

## 2026-11-23 independent saved media checkpoint

`saved_media_audit.py` independently checks the source-index seal and six original JSON file hashes, then joins and fully decodes all 600 frames from each of four cameras against the original Native frame/time map. It rejects changed original PNG bytes, shifted source files, invalid camera paths/profiles, missing views and frame gaps. A retained fake-adapter fixture under `.runtime-work/c111610-media-proof-v1/` passed: `saved-media-diagnostic.json` SHA256 35d19bd60a5d67a00db15b39b5658230971a94ed9ac00e4bc3728de8e86f2df2, `saved-media-proof.log` SHA256 b70ce35605a29d90e425c4a9b75921946f8e78640beb9a4c40aa479d0b752c99. The report explicitly marks `synthetic_fixture`, leaves pixel visibility unreviewed and physical acceptance false.

Focused 29-test suite passed (`cpu-tests.log` SHA256 6784e234f8711c09d6ac40b7d8058f8c83c6242317566f6e97fab3068c8eb640); pinned preflight passed (`cpu-preflight.log` SHA256 d875096aa9571dc8a8d95f70ea21a10b174ce6012f7f3f3d4cbd75d3798c7163). This is a software source-integrity checkpoint. Original Native site/CARLA source validation, exact inline bundles, offline/compatibility, semantic stages and delivery acceptance still require construction.
Scoped static `check-complete.log` exit 0 SHA256 e5747523924cafcfcb63f346271e3ef25d46c51d37527c8af4b11f5026889978; exact strict `check-strict.log` exit 1 on truthful partial SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-24 saved delivery clock join checkpoint

`saved_delivery.py` now reprocesses source-sealed actor measurements and independently decodes all 2,400 original camera PNGs for one exact 600-frame attempt. It joins the ego and pedestrian original Native frame/time fields to the camera frame map on every tick, verifies case/scene/source-index identity, and writes a source-hashed saved receipt. A resealed actor-clock mutation is rejected even though each earlier independent processor accepts its own input. The retained fake-adapter diagnostic succeeds and explicitly leaves physical provenance, pixel visibility and legal judgment unresolved.

The focused suite passed 31 tests, pinned preflight and scoped static passed, and exact scoped strict exited 1 on truthful partial. SHA-bound commands and logs are in `result.json`. Remaining CPU construction: original reviewed Native site and CARLA adapter, seven canonical inline bundles and manifest, semantic stages, pinned offline/compatibility receipts, and complete saved delivery/comparison acceptance.

## 2026-11-24 lazy CARLA adapter checkpoint

`carla_adapter.py` now supplies the capture writer from a synchronous original world at exactly 20 Hz. It binds the site file hash and live map name, requires two distinct actor IDs, reads actual tick/snapshot frame and elapsed time, both actor body centers and ego brake readback, and requires four original camera PNG readers to return the same Native frame. It rejects a changed site/map, unsynchronized world, camera frame mismatch, invalid brake/pose and overlapping actors. The operator still owns the world lease, source-reviewed survey, sensors, controller and actor cleanup. The adapter does not establish physical motion or visible pixels.

`tests/test_carla_adapter.py` runs a complete 600-frame fake-world adapter through `native_capture.capture` and the existing saved actor/camera join, then exercises source, world, camera and actor rejections. The focused suite passed 33 tests (`cpu-carla-adapter-tests.log`, SHA-256 `4e00dd25ac2201d5d9466ee368d5ed46a17cf8c6dc7c556f6a24b017062cacea`). Pinned preflight passed (`cpu-carla-adapter-preflight.log`, `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`); scoped static passed (`cpu-carla-adapter-static.log`, `e5747523924cafcfcb63f346271e3ef25d46c51d37527c8af4b11f5026889978`); exact scoped strict exited 1 on truthful partial (`cpu-carla-adapter-strict.log`, `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`). `result.json` binds all four logs. Synthetic media and scratch stayed under `.runtime-work/`.

Remaining CPU work: review and bind the original map/site and exception sources, wire the production controller and four sensors with local cleanup, author seven canonical construction bundles/manifest and semantic proposals, then run exact offline, positive/negative compatibility, saved processing and independent delivery/comparison acceptance. Physical motion and pixels remain future local review.

## 2026-11-24 synchronous live world ownership checkpoint

`live_crosswalk.py:run` now leases a Native world for 20 Hz synchronous capture, requires the injected source-reviewed scene factory to register six distinct ego/pedestrian/four-camera actors, connects `CarlaNativeAdapter` to the complete 600-frame `native_capture.capture` source writer, and restores world settings and destroys registered actors even when the factory fails partway through. The factory itself still must provide a reviewed site, concrete sensor configuration and controller; this wrapper does not assert physical completion.

The 35-test suite, pinned preflight and scoped static pass, including a full fake-world 600-frame capture and partial-factory cleanup. Exact scoped strict exits 1 on truthful partial. Four SHA-bound logs are in `result.json`. Remaining CPU: concrete reviewed-site scene/sensor/controller factory, seven canonical bundles/manifest, semantic proposals and pinned offline/compatibility/process-saved and independent delivery proofs. Actual motion and pixels remain unverified.

## 2026-11-24 concrete live scene factory checkpoint

`carla_scene_factory.py` connects the synchronous wrapper to a source-gated original map/site packet, case-specific source-reviewed pedestrian route, original exception review, two distinct CARLA participants, and four 20 Hz RGB sensors. Its camera readers bind each original sensor frame and decode complete BGRA payloads to PNG. The controller follows original turn and pedestrian route waypoints with bounded speed; it holds the ego for an occupied destination-half crosswalk, an operating official device, unresolved exception, or opposite-half danger that lacks an independent review. These are engineering controls, not a legal yield verdict. `live_entrypoint.py` imports CARLA only on execution and requires reviewed site and exception files.

The new factory tests exercise four sensor creation, participant control, missing source route, contradictory device condition, original frame mismatch and BGRA channel decoding. The full 38-test assignment suite passed (`cpu-scene-factory-tests.log`); scoped static `worker_check.py --assignment ... --complete` passed (`cpu-scene-factory-static.log`). Both log hashes are in `result.json`. All generated test media stayed under `.runtime-work/`. Status remains partial.

Next CPU work is to seal and test a dynamic original official-device readback for every Native frame, finish seven exact inline constructions and finalizer/diagnostic recipes, then bind semantic proposals, official offline/compatibility/saved proofs and independent delivery/comparison audits. An original reviewed map/site packet and exception source must be supplied for a live attempt. Physical camera coverage, movement and any legal result remain unverified.

## 2026-11-24 canonical runner bootstrap

`runner.py`, root `config.json` and `scene.json` now bind the first selected destination-occupied/absent exact case, the seven-case support inventory and the 20 Hz, 600-frame, 30-second, four-view capture profile. The runner hashes the selected scene and validates the fixed law/cell/actor before lazy CARLA import. Runtime materialization still requires per-case inline constructions, finalizer and canonical manifest; these root files are bootstrap artifacts, not a delivery claim.

`carla_scene_factory.py` now also checks that the source-reviewed pedestrian route starts in the planned crosswalk and directional-half region. Two new runner tests and a wrong-region rejection test bring the full suite to 41 passing tests (`cpu-runner-factory-tests.log`). Scoped static check passed (`cpu-runner-factory-static.log`). Both logs are SHA-bound in `result.json`; status is partial.

## 2026-11-24 seven exact inline offline constructions

`build_inline.py` authored seven separate exact-case `construction.json` files, with root `construction.json` for `destination_occupied_absent`, and a partial `execution-manifest.json`. Each construction embeds the current source modules, its own sealed `scene.json`, selected `config.json`, eight observation channels, 20 Hz/600-frame/four-view profile and a materialized bundle test. The offline bundle test checks exact selected identity and capture contract; it does not simulate the crossing or establish physical completion.

Pinned `runtime.py offline --manifest ... --case CASE --output .runtime-work/c111610-283/offline-v2-SUFFIX` passed separately for all seven exact case IDs. `proof-offline-SUFFIX.log` files and their SHA-256 bindings appear in the manifest and `result.json`. No scratch was returned under `work/`. Scoped partial `worker_check.py --assignment ... --complete` still passes. The selected manifest remains partial because it does not yet bind finalizer, semantic proposals, compatibility/saved proofs, physical preparation, risk-based fallbacks or independent delivery/comparison acceptance.

## 2026-11-24 canonical semantic proposal proof

- Nine-stage direct validator passed for seven exact case IDs; proof: `proof-semantic.log`; proposal index SHA `4c5cfe65ac579c8da7f623f822cbf5e9956787c851e118a43e48f5ec26d9a2d5`.
- Four judgment phrases and the source-dependent judgment sweep remain explicitly unresolved. No legal or physical acceptance was inferred.
- Status remains partial while saved analysis finalizer and selected diagnostic compatibility remain unfinished.

## 2026-11-24 saved analyzer milestone

- Added selected `analysis.py` to all seven exact inline constructions. It joins sealed actor, crosswalk, device, exception and 2,400 original camera frame sources; derives 600 trace/map rows, ten recording evidence channels/contexts and four lossless camera video streams without changing capture bytes.
- `proof-saved-analysis.log` records a synthetic 600-frame diagnostic that passed the existing native result validator. Its result has `rebuild_required=true`, `setup_confirmed=false`, `maneuver_completed=false` and no legal verdict. This is software evidence only.
- Regenerated and reran all seven pinned offline proofs after embedding the analyzer. Forty-two assignment tests passed in `cpu-finalizer-tests.log`.
- Compatibility recipe/measurement contract and negative case-source proof, genuine original site and Native motion proof, same-case physical fallback, saved processing and independent delivery/comparison bindings still remain. Status is partial.

## 2026-11-24 same-case physical fallbacks

- Every exact case now has one distinct `fallback1` construction. It keeps law, cell, actor, pedestrian condition, exception/device branch, four cameras, 20 Hz and 30 seconds fixed, while reducing the same turn-route engineering target speed from 4.0 to 2.5 m/s if original frame evidence shows insufficient pedestrian observation overlap or blur. This is a predeclared physical repair trigger, not a legal outcome choice.
- The pinned candidate-construction invariant validator passed for all seven entries (`proof-fallback-structure.log`). Primary and fallback each passed pinned offline proof, 14 total. Positive/negative compatibility for both candidates is still required; no fallback is ready.

## 2026-11-24 selected measurement contracts

- `build_measurement_contracts.py` writes seven case-specific contracts for every selected frozen requirement (3–5 per case). Each binds a named `analysis.py` method, output type, and exact retained source files. All seven passed the pinned measurement contract structure validator.
- `proof-measurement-contracts.log` verifies the occupied-destination diagnostic report against exact source hashes and confirms removing `capture/exception_review.json` fails with the required case-source error. This is diagnostic software evidence; other exact cases still need their generated positive/negative compatibility and saved processing proofs.
- After adding the methods, all 14 primary/fallback inline bundles were regenerated and reran pinned offline proof. The 42-test assignment suite passed again in `cpu-measurement-tests.log`.
