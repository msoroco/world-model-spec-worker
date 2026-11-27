# testing__C111329__NRS-484B-287-1c__pedestrian

Status: ready, delivery prepared by the 2026-11-25 final scoped strict gate. Three selected case bundles and their CPU proof paths are built. No reviewed original C111329 site, Native recording, physical acceptance, or legal verdict is claimed. The dated checkpoints below record prior work; the final section is current.

Exact source: NRS 484B.287(1)(c) in frozen `inputs/testing__C111329__NRS-484B-287-1c__pedestrian/assignment.json`; witness 390 is conditional and frozen accepted evidence lists zero recordings. The NRS 484B.290 exception remains unresolved.

## Exact cases and comparisons

- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_operating`: crossing outside surveyed marking with both devices operating.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_marked_operating`: same crossing station within surveyed marked crosswalk.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_inactive`: same unmarked crossing, one device inactive.
- `between_intersections_marking` holds site, station and operation fixed; `both_devices_operating` holds site, station and marking fixed. See `case-plan.json` for source gaps, risks and observation mappings. These are planned cases, not recordings.

## Implemented CPU construction and audit

`site_geometry.py` requires SHA-matched map, route, device, marking and highway sources and exact packet-to-source content equality. It checks two distinct junctions, direct source edge, no intervening junction, route crossing both highway banks, strict station between junction envelopes, authority/placement/purpose/governance fields and operation intervals at both devices, and a complete marking survey. It returns legal adjacency, legal official status and the NRS 484B.290 exception as undetermined. Source record IDs are prerequisites for review, not legal conclusions. `native_route.py` lazily spawns a source-selected CARLA walker and applies route controls with readback and cleanup on rejection. `comparison_audit.py` rejects changed fixed sources and conditions. Both crossing directions are CPU-tested.

`native_observation.py` captures original contiguous 20 Hz world frames, walker positions, and two source-identified device actor/state/operation readbacks. Its saved-only analyzer verifies the exact case and site source hashes, complete frame sequence, device identities, and physical bank-crossing segments. It reports device operation over the observed crossing frames separately from all-frame operation; it leaves legal adjacency, official status, and NRS 484B.290 unresolved. The production default is 900 ticks. Caller must bind the device reader to real Native actors and provide a reviewed source packet; fixture readbacks do not establish physical operation.

The capture now takes four named frame-synchronized original PNG readers using the pinned overview1080-capability dimensions (1920x1080 overview, three 1280x720 detail views), stores one lossless archive per camera, and binds each PNG SHA256 to its 20 Hz observation row. `saved_camera_audit.py` independently verifies all archive hashes, frame maps, per-frame PNG hashes, dimensions and full pixel decodes before returning the saved motion analysis. It rejects a missing camera, archive tamper and changed frame binding. A 900-tick CPU fixture decodes all 3,600 images; it uses tiny injected dimensions and does not establish camera visibility or Native capture quality. The caller must supply real per-frame CARLA camera readers and run the saved audit at the pinned dimensions.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1c__pedestrian/tests -v` passes 27 tests; SHA256 of `cpu-tests.log` is 9caf5bd0833aa492be5815849cdd43e89324ce6feee01b6bd8223bacc021900a. `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete` passes; SHA256 of `cpu-static-check.log` is 2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe. These are source-shaped fixtures, not physical evidence.

`.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` failed with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log` (SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a). The result remains partial.

## Next CPU actions

1. Bind a real map and two device actors to the frozen C111329 scene, validate original map topology and connect the real 20 Hz device and four camera readers for each case. Resolve the fixed intersection layout against the required between-intersection segment without inventing a new cell.
2. Add per-case config, construction, manifests, finalizers, diagnostic recipes and source-bound positive/negative compatibility/offline/saved-only proofs. Build semantic stage proposals and an independent delivery audit.
3. Review the NRS 484B.290 exception and legal meaning of adjacent intersections/official devices independently from the geometry packet. Do not infer them from record IDs or visual appearance.
4. Rerun the tests and exact strict gate; mark ready only after it passes. Physical motion, actual map site, camera coverage and recordings remain later Native checks once CPU preparation is complete.

## 2026-11-23 CARLA readback bridge checkpoint

Added `carla_readback.py`, a lazy bridge from four named CARLA BGRA camera callbacks to the exact frame-indexed PNG readers consumed by `native_observation.capture_observation`. It checks dimensions and byte count, bounds pending callback frames, rejects duplicates/missing frames, and consumes each frame exactly once. Its device reader binds each source device ID to a distinct original actor, reads the actor state, and requires a separate boolean operation-health callback; a color state is not treated as operation evidence. The caller remains responsible for selecting real source-grounded actors/sensors, creating them, setting 20 Hz synchronous mode, and cleaning them up.

`tests/test_carla_readback.py` exercises a full five-frame four-camera capture through the bridge, mismatched/duplicate frames, malformed BGRA, duplicate actor IDs, and missing operation evidence. `carla_readback.py` SHA256 `3cfe8c4da879e96da30f91ecf04857384fdde219f54767868f2ec1c3e13e62e0`; test source SHA256 `12a00586faa0cee246ad1e870c233a6cf416fd36357b3805cbc4a6959e2b535e`.

Pinned CPU proofs: `cpu-tests.log` (30 tests, exit 0) SHA256 `e756aef84bf0b8067efa7dbe42558b926ffb00be2af37186986e2631fd48e6bc`; `cpu-preflight.log` (exit 0) SHA256 `71b5e75c8e8b6dfe5d820a79cd7642e5fe17ba3e034cbe8783eb50859177a352`; `cpu-static-check.log` (exit 0) SHA256 `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`. Exact assignment strict check exits 1, `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`, because the package remains truthful `partial`.

Next CPU work: obtain/review the exact fixed-cell map, device authority/operation and complete marking survey sources; bind three case-specific runners and finalizers to those sources; create canonical stage proposals and saved-only positive/negative compatibility plus independent delivery receipts. Legal adjacency, official-device status and NRS 484B.290 still need independent source-supported review. No live CARLA or legal acceptance is claimed by the CPU fixture.

## 2026-11-24 route-control integration checkpoint

Added `owned_capture.py` and a `before_tick` hook in `native_observation.py`. The wrapper source-checks and spawns the route walker, applies `advance_pedestrian` immediately before each world tick, and destroys the actor on both capture success and failure. The capture rejects a noncallable hook or a hook failure without leaving an original observation. This closes a control timing gap; it does not establish a reviewed Native site, device operation or legal outcome.

Focused suite: 34 tests pass. Pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. SHA256 receipts:
- `cpu-route-integration-tests.log`: `5cdab3d500e21a0333807024efb87c1de6fa8f5d1ab2f6f1690cd265534a32ba`
- `cpu-route-preflight.log`: `ea55fdb989d1827c213c923af4284a1d85b33429dd7d7a01f58038f1fed484b9`
- `cpu-route-static.log`: `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`
- `cpu-route-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Next: bind reviewed fixed-cell map, device authority/operation and complete marking survey; build exact per-case production bundles/finalizers, canonical proposals and saved positive/negative compatibility with independent delivery audit. Legal adjacency, official-device status and the NRS 484B.290 exception remain unresolved.

## 2026-11-25 selected CPU delivery checkpoint

`execution-manifest.json` is the canonical selected three-case manifest, SHA256 `38315b7b7f3c72009489fca1caf2fc4f388313a71927c10a5f4449bbc727706e`. It has zero `manifest.draft` command references and binds primary and fallback construction, offline and compatibility proofs, saved-only and independent delivery commands, physical preparation receipts, and two comparison audits. `proposals/` contains semantic stage and pending-source judgment proposals. Every physical and legal acceptance flag remains false.

All six primary/fallback CPU offline and positive/missing-site compatibility proofs passed. `cpu-offline-proofs.json` and `cpu-compatibility-proofs.json` index the receipts. All six final compatibility runs used `.runtime-work/c111329-287-1c-compat-v9-<case>-<candidate>` and the assignment-local Lean validator. Their receipt hashes equal the canonical bound hashes, and every `candidate-selection.json.manifest_sha256` equals the canonical manifest SHA above. `run_compat_deterministic.py` clears and recreates only its `.runtime-work/c111329-287-1c-fixture-stable/` negative fixture path; this stabilizes the negative traceback receipt while still calling frozen `package_compatibility.run`.

Three selected saved-only positive runs passed with `missing_evidence=false`; three missing-site runs passed with `missing_evidence=true`. They used v9 primary attempts and retained recorded originals. `cpu-saved-proofs.json` hashes the current per-case processing receipts, analysis logs, and negative feedback. Three independent positive delivery audits decoded 900 frames and all four encoded camera sources per case. Three negative audits exited 1 on `Missing required source: effective-site-packet.json`. Their v9 receipts and logs are byte-identical to the indexed `cpu-independent-proofs.json` and `cpu-independent-negative-proofs.json`. `cpu-comparison-proofs.json` binds both measured diagnostic source comparisons to these independent receipts. Three `cases/*/physical/receipt.json` triads exercise complete-motion, incomplete-motion, and missing-evidence paths, all diagnostic only.

The diagnostic packets under `cases/*/diagnostic-sources/` are fixtures. The frozen accepted evidence inventory has zero recordings; no reviewed original fixed-cell map, route, complete marking survey, highway banks, two device authority/placement/operation records, or Native site packet was supplied. Adjacent-intersection meaning, official-device status, and NRS 484B.290 exception applicability require independent source-supported review. The 900-frame four-camera CPU fixture proves processing, not Native camera coverage or physical completion.

Scratch is intentionally outside returned `work/`. Rebuild the assignment-local validator before replaying compatibility or saved-only commands:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py build-decoder --library runtime/library --output .runtime-work/c111329-287-1c-decoder --lake /lustre/fsw/portfolios/av/users/wcong/tools/bin/lake
```

Pinned Lean/Lake is 4.28.0. The built `.runtime-work/c111329-287-1c-decoder/.lake/build/bin/adapterCheck` SHA256 is `0500e6edb8d441c540260373550f8855a77ef9f31dd216875a901ff162e0c614`. Every direct pipeline import must set `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/`; all temporary directories belong there.

Final scoped checks:

- `cpu-v9-tests.log`: 45 tests, exit 0, SHA256 `3a060839a085eac0de54da0bdd095f9d492344699d1b416081f68412894df253`.
- `cpu-v9-preflight.log`: pinned CPU preflight, exit 0, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `cpu-v9-static.log`: exact assignment `--complete`, exit 0, SHA256 `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`.
- `cpu-v9-strict.log`: exact assignment `--complete --require-delivery-ready`, exit 1, SHA256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`. The checker reaches its status gate and reports `Preparation acceptance failed: partial/missing packages remain` because `result.json` truthfully remains partial.

The next step is to bind the reviewed original fixed-cell sources and actual Native attempts for each case, then replay source-bound proofs and independent physical/comparison review. Keep `result.json` partial until its strict assignment gate passes.

## 2026-11-25 final selected delivery and original-source audit

The selected manifest `execution-manifest.json` SHA256 is `ae3babb75f21fc374b99d31c7b1cd038796434ed9dbfb310f366b0d0f69a1abc`. The exact selected cases are `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_operating`, `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_marked_operating`, and `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_inactive`. The controlled comparisons are `between_intersections_marking` and `both_devices_operating`. All six current-runtime primary/fallback compatibility receipts were regenerated against the selected constructions. Three physical preparation receipts were refreshed to bind those same constructions, each with complete, incomplete and missing-evidence fixture outcomes. This is software preparation; no original Native recording was created.

`production_delivery.py` is the production source audit. The local operator supplies the sealed original attempt and a SHA-bound independent physical review reference. The audit independently reopens the original site packet, observation, trace, frame map, four PNG archives, four 900-frame encoded camera streams and Native acquisition/restoration seal, then checks the physical review against the exact observation, seal, camera hashes, site sources, crossing frames and case distinction. A diagnostic attempt or missing review is rejected. The command for each exact case is:

```sh
mkdir -p "$PWD/.runtime-work/c111329-287-1c-production-audit"
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.runtime-work/c111329-287-1c-production-audit" SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c111329-287-1c-production-audit" .venv-cpu/bin/python work/testing__C111329__NRS-484B-287-1c__pedestrian/production_delivery.py --case-id "$CASE_ID" --attempt "$ORIGINAL_ATTEMPT" --physical-review-ref "$SEALED_REVIEW_REF" --output "$AUDIT_OUTPUT"
```

`production_comparison.py` invokes that production audit separately for both original attempts, then checks fixed source hashes, duration/camera policy, exact case order and the declared marking or device-operation difference. Each comparison uses:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.runtime-work/c111329-287-1c-production-audit" SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c111329-287-1c-production-audit" .venv-cpu/bin/python work/testing__C111329__NRS-484B-287-1c__pedestrian/production_comparison.py --comparison-id "$COMPARISON_ID" --reference-attempt "$REFERENCE_ORIGINAL_ATTEMPT" --variant-attempt "$VARIANT_ORIGINAL_ATTEMPT" --reference-review-ref "$REFERENCE_SEALED_REVIEW_REF" --variant-review-ref "$VARIANT_SEALED_REVIEW_REF" --output "$COMPARISON_OUTPUT"
```

The focused CPU suite passed 48 tests (`cpu-current-tests.log`, SHA256 `b2ff0d8c3f432feeda3b40ac9a1ab5589b4d372ad60cc991325cfa1a11ae292e`). Pinned preflight passed (`cpu-current-preflight.log`, SHA256 `0e0bee4532568ab3b637917d9f06920b623981ecfd4a2124144d49b1033ac000`). The exact `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` command exited 0 with `static_checks_passed: true` (`cpu-current-strict.log`, SHA256 `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`). The result is `ready` with `readiness_kind: delivery_prepared`, limited to CPU preparation. A reviewed original fixed-cell site, complete marking survey, two official device authority/operation sources, NRS 484B.290 exception review, actual Native motion, four-view visibility and independent original physical/comparison acceptance remain local execution and review work. No legal verdict or physical acceptance is claimed.

## 2026-11-27 saved-only post-capture closure

Full-branch review found the selected manifest omitted `post_capture` for all three exact cases. The binder contained an unexecuted draft referencing `runtime.py feedback`, a command absent from the current frozen CLI. `result.json` was demoted while the CPU repair ran. The selected manifest and binder now bind each case's `post_capture.command` and `feedback_command` to the executable `runtime.py process-saved` path with exact case, saved attempt, derived output, pinned library/validator, and owner-release receipt. That path processes originals without CARLA and writes case-specific `feedback.json` when an original source or processing step fails. Each post-capture entry also binds the existing positive saved receipt and missing-site feedback receipt with SHA256.

`prove_post_capture.py` reran each bound command on a copied source-shaped synthetic diagnostic attempt, with a synthetic lifecycle receipt and current manifest selection hash. All three passed with `recorded_only: true`, `originals_preserved: true`, `missing_evidence: false`. It verified the retained three missing `effective-site-packet.json` feedback receipts (`recorded_only: true`, `native_replay_requested: false`) and exercised all three exact feedback commands on absent originals; each emitted case-bound failure feedback and exited nonzero. The synthetic attempt and temporary outputs stayed under `.runtime-work/`. This proves software behavior only; it does not attest actual owner release, source review, physical completion or legal applicability.

Proof command `.venv-cpu/bin/python work/testing__C111329__NRS-484B-287-1c__pedestrian/prove_post_capture.py` exits 0; `cpu-post-capture-20261127.log` SHA256 `8861ddeddf0e579fb60d0d3b5eb1745451af56ab6c248166c2f2c25bbb520e08`. The 48 assignment unit tests pass; `cpu-tests-post-capture-20261127.log` SHA256 `582079d2859fafc57a399eab1d8a867414042423b008e76a6118564346c95931`. Exact `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` exits 0; `strict-post-capture-20261127.log` SHA256 `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`. The assignment status was restored to `ready` after this strict pass. Local original Native acquisition, independent physical/pixel review and NRS 484B.290 exception review remain outstanding.
