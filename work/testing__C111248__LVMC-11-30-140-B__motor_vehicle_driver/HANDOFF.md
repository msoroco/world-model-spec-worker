# testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.140(B) — Any pedestrian who is not wholly or partially blind, or any driver of any vehicle who approaches or comes in contact with a person wholly or partially blind, carrying a cane or walking stick white in color, or white tipped in red, or being assisted by a person with wisdom, shall immediately come to a full stop and take such precautions before proceeding as may be necessary to avoid an accident or injury to the person wholly or partially blind.
Assigned branch(es): Driver approaching a blind person carrying a white cane..
Cell: C111248 (intersection, travel, blind_pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

The full statute was reread. The fixed role is motor-vehicle driver; the cases in `case-plan.json` preserve the white-cane assigned branch and add red-tipped cane and assisted-person cue alternatives, approach/contact observations, full-stop/rolling response, and precaution timing. Five controlled comparisons reuse the white-cane full-stop reference. These are planned cases, not physical recordings or legal outcomes. No accepted recordings exist in frozen `evidence.json`; the case-plan review records that exact gap. No exact-law judgment ranges were inventoried.

`blind_encounter.py` now plans source-gated Native map/route/actor identity and separately requires independent blindness attestation plus carried-cue source. `construct_native` calls adapter map lookup and actor/prop construction with readback and reverse-order cleanup; it does not infer blindness from actor appearance. `measure_saved` validates contiguous original 20 Hz rows and measures approach, stop, proceeding, contact, gap and precaution fields. `audit_comparison` rejects missing evidence and changed fixed identities/capture sample counts. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/tests -v` passed 4 tests; log `cpu-tests.log`, SHA256 87f6f5c69c9b38d907ffb2e1e22f0f9258ad3605993952ce72175d70a89efef0.

Exact strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver --complete --require-delivery-ready` exits nonzero with `Preparation acceptance failed: partial/missing packages remain`; see `strict-check.log`. Continue with exact runner/config/construction bundles for all six cases, canonical stage proposals, case-specific diagnostic recipes and offline/positive/negative compatibility receipts, saved-only postcapture path, independent delivery audits, and source-bound comparison proof receipts. The contact case requires risk review before any physical attempt; the code never commands collision. Do not mark ready until the exact strict gate passes.

## 2026-11-24 saved-only source-binding checkpoint

`saved_encounter.py` now processes a closed original-history JSONL together with separately stored blindness-attestation and carried-cue JSON. A small manifest binds each by SHA256, exact assignment and case, and expected frame count. It rejects missing or escaping paths, changed source bytes, incomplete original history, missing independently stated blindness basis/issuer and a cue without an actually-carried observation source. It invokes `blind_encounter.measure_saved`, retains all source hashes in the output, and explicitly leaves physical acceptance false. This is CPU code and fixture proof only; no such real sources have been acquired for this assignment. The test inputs' issuer and observation names are diagnostic fixtures, not verified real-world attestations.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/tests -v` passed 8 tests in `cpu-tests.log` (SHA256 `844e16c04ebcd8727a453d535f70a4d76c3d76c1f494cc077ca2189167d423cf`). The path can be exercised after a real attempt as `.venv-cpu/bin/python work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/saved_encounter.py --manifest ATTEMPT/saved-manifest.json --output ATTEMPT/encounter-measurement.json`; it is not yet integrated with the canonical runtime process-saved finalizer. Next CPU work: Native 20 Hz controller and capture integration, exact case bundles and semantic proposals, positive/negative compatibility receipts per case, independent delivery audit, and stronger comparison checks across distinct Native run actor IDs.

## 2026-11-24 original Native capture and media audit checkpoint

`native_capture.py` now defines a lazy adapter path for all six exact case plans: 900 contiguous Native ticks at 20 Hz, original person/body observations, bounded braking policy, and four synchronized PNG sources per frame. It requires separate source files for blindness attestation and an actually carried cue, and never commands contact. The adapter is always asked to stop and close after the loop. `delivery_audit.py` independently reopens and fully decodes all 3,600 original PNGs, checks dimensions and exact frame/camera joins, and rejects stale hashes or rebound paths. `saved_encounter.py` calls this audit when the media map is supplied. These are software fixtures only; physical visibility and attestation still require local review.

Focused command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/tests -v` passed 11 tests (`cpu-tests.log`, SHA256 fc230d8146618bef00dd4e3518a4112aa716040c6f95770e949508a8193a8b24). Exact scoped `--complete` static check passed (`static-check.log`, SHA256 0a4ff9e3e5d8205601b12039ecd202fc0159418643bff694b18cd0939c6dff4f). Exact scoped `--complete --require-delivery-ready` failed because result remains partial (`strict-check.log`, SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a).

Next CPU actions: integrate this adapter with per-case executable Native runner and canonical runtime finalizer; author source-hashed semantic proposals and all exact case bundles, diagnostic recipes, offline and positive/negative compatibility receipts; test saved-only postcapture and each controlled comparison end to end. No legal cutoff has been supplied for immediately or necessary precautions.

## 2026-11-23 lazy CARLA actor and camera adapter checkpoint

`carla_adapter.py:CarlaAdapter` now implements the `native_capture.capture` adapter protocol for a borrowed synchronous 20 Hz world, distinct driver and protected-person actors, four original RGB camera sensors, and an injected independently sourced encounter-context reader. It checks consecutive post-tick world snapshots, finite actor position/velocity, actor IDs, context booleans and camera callback frame identities; it converts original BGRA buffers to PNG. A measured 2D circle-bound gap is labeled a proxy and never treated as contact or legal necessity. It applies bounded vehicle control and brakes/stops sensor listeners on exit. The caller still owns actor/sensor spawning, world restoration, blindness attestation and actually carried cue sourcing.

Fourteen focused CPU tests pass (`cpu-carla-adapter-tests.log`, SHA256 `fc0faeef63dc481c181b7486857b1beb0317e3f1f28a7b9a26c3ce12a284ddeb`). Pinned preflight exits 0 (`cpu-carla-adapter-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Scoped static exits 0 (`cpu-carla-adapter-static.log`, SHA256 `0a4ff9e3e5d8205601b12039ecd202fc0159418643bff694b18cd0939c6dff4f`). Exact scoped strict exits 1 on truthful partial status (`cpu-carla-adapter-strict.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: bind verified real blindness/cue and protected-person identity sources, implement exact per-case canonical bundles and semantic proposals, positive/negative compatibility, canonical saved processing and independent comparison proof receipts. The contact case remains observation-only and risk-gated; no collision is commanded.

## 2026-11-23 six-case diagnostic construction checkpoint

`build_offline_draft.py` now packages all six exact planned cases with source-hashed embedded `case-plan.json`, distinct cue/encounter/response/precaution knobs, the existing Native actor and camera adapter, 900-frame original capture, saved measurement and pixel audit. The bundled runner validates case identity, case knobs, 20 Hz/45-second profile and required source inventory, then refuses a Native launch without reviewed map, blindness and actually carried cue sources. The contact case remains observation-only and never commands a collision.

All six exact pinned `runtime.py offline` constructions pass. Pinned preflight, 14 focused tests and scoped static pass. The exact scoped strict gate exits 1 on truthful partial status. These are diagnostic bundles, not canonical delivery. Next CPU work is production runner/source packet binding, semantic proposals, compatibility, saved-only runtime processing and independent delivery/comparison receipts. No physical blindness, cue visibility, stop necessity or legal judgment is claimed.

Current proof SHA-256 receipts:

- `cpu-bundle-preflight.log`: `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63` (exit 0)
- `cpu-bundle-build.log`: `d51b1b918534bc1261bf61fff2b9b7417ca593460d43e4121aa9480bbe43604c` (exit 0)
- `cpu-bundle-offline-white_full_stop_wait.log`: `88040f968f83d5aa4e6095a780d52f6b8622822018b3a45d5750914fedd39374` (exit 0)
- `cpu-bundle-offline-white_roll_through.log`: `fd1fc49aac2f8dc434fcec6a1d1591343f6b96c844b506697b957a57ddbc2031` (exit 0)
- `cpu-bundle-offline-white_early_proceed.log`: `d48ddf3303610a70384145095010f7eb9913545a865b90ac9700b9bf928c42c9` (exit 0)
- `cpu-bundle-offline-white_contact_stop.log`: `94f93a05af8c149572696c6e0684fbe3e621d5e1e4ca1083f6f347464c0e9691` (exit 0)
- `cpu-bundle-offline-red_tip_full_stop_wait.log`: `a4920d06b3ca91cca1cc69a1bf272b190856c011a8066e2b210d129db26f6a70` (exit 0)
- `cpu-bundle-offline-assisted_full_stop_wait.log`: `79549598ad270e45226b4c057866c0dfe8650813190b833fee3ef251e4ecec0a` (exit 0)
- `cpu-bundle-tests.log`: `7b10f312d54751897f2d2928c9005820c871814b7b5f0a502ab54a74555e2bcc` (exit 0)
- `cpu-bundle-static.log`: `0a4ff9e3e5d8205601b12039ecd202fc0159418643bff694b18cd0939c6dff4f` (exit 0)
- `cpu-bundle-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

## 2026-11-23 saved output custody and six-case rebundle

`saved_encounter.process` now refuses an existing or symlinked output before it reads sources and uses an exclusive final create after all checks. A repeated saved-only run cannot replace a prior source-bound measurement; the new focused test proves byte preservation. The exact diagnostic bundles were rebuilt with this code and all six pinned offline constructions passed again. The focused suite passes 15 tests, pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful `partial`. Canonical semantic stages, real reviewed blindness/cue and map sources, positive/negative compatibility, runtime saved-only delivery and comparison receipts remain. The contact case is observation-only.

Current refreshed CPU log SHA-256 receipts:

- `cpu-bundle-build.log`: `d51b1b918534bc1261bf61fff2b9b7417ca593460d43e4121aa9480bbe43604c` (exit 0)
- `cpu-bundle-offline-white_full_stop_wait.log`: `2e70d1284ec0672c46c3f45ac6425b0d309513edd6b436d7c8307bbe1526a719` (exit 0)
- `cpu-bundle-offline-white_roll_through.log`: `f48b835bf27abc473cd9073306b3aba675207798dbbfde471b7c400a16e69dd4` (exit 0)
- `cpu-bundle-offline-white_early_proceed.log`: `2bdd7ef9f4d5359625a1c57a61976f557f132ab3d0c794f335144198cc7081b1` (exit 0)
- `cpu-bundle-offline-white_contact_stop.log`: `0e090932003b2e8d9bb7b3a36f122ad515b34632199ea1a1dc06a24608e38017` (exit 0)
- `cpu-bundle-offline-red_tip_full_stop_wait.log`: `dec0f3f8e231667d09f397f6a74f510756a0052dc8acc130e83b5473014623ac` (exit 0)
- `cpu-bundle-offline-assisted_full_stop_wait.log`: `39e638c70033f51440849d7a1a7f581842c5ee925a4bea2db43b551ea2a7a4ce` (exit 0)
- `cpu-bundle-tests.log`: `d84fd8b0f2f9e5d9619c99a65221b5c0f0fb8c384fbb064140e521d704bc25c4` (exit 0)
- `cpu-bundle-static.log`: `0a4ff9e3e5d8205601b12039ecd202fc0159418643bff694b18cd0939c6dff4f` (exit 0)
- `cpu-bundle-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

## 2026-11-24 reviewed original-source packet checkpoint

`reviewed_sources.py` now loads five distinct source files: reviewed original Native map/route, blindness reviewer metadata and original, and carried-cue reviewer metadata and original. It binds each by SHA256, requires the original evidence bytes named by the reviewer records, validates exact person/driver IDs, cue, map and finite route, and calls `blind_encounter.plan_native`. Diagnostic case bundles include this planner and accept an optional `--source-packet`; they still refuse physical launch until local Native actor/world ownership is integrated. Fixtures in the three new focused tests are explicitly synthetic and do not claim real blindness or cue visibility.

Pinned preflight, 18 focused tests, six rebuilt offline constructions, and scoped static pass. Exact scoped strict exits 1 on truthful partial. See `result.json` for commands and SHA256 logs (`cpu-reviewed-*.log`). Next CPU work: acquire reviewed map/blindness/cue originals from the authorized local source process, integrate a Native spawn/world-restoration runner, canonical semantic proposals and six positive/negative compatibility proofs, saved-only processing and comparison receipts. Contact remains observation-only.

## 2026-11-24 reviewed capture entrypoint checkpoint

`native_capture.capture_reviewed` now calls the SHA-bound reviewed-source packet before any capture, checks exact case identity, invokes the existing original 900-frame capture with those attestation/cue files, and seals map and evidence hashes in the saved manifest. The new test checks that the reviewed files are passed to capture and that another case is rejected; the production caller still must own actor creation and world restoration.

The latest focused suite passes 19 tests (`cpu-reviewed-tests-v3.log`). Rebuilt all six diagnostic bundles after embedding this entrypoint; each pinned offline command passes (`cpu-reviewed-v2-offline-*.log`). Pinned preflight and scoped static pass, exact scoped strict remains exit 1 on truthful partial (`cpu-reviewed-strict-v3.log`). All current SHA receipts are in `result.json`. Canonical semantic proposals, positive/negative compatibility, saved delivery and comparison receipts, plus local reviewed originals and Native world/actor ownership are next CPU tasks.
