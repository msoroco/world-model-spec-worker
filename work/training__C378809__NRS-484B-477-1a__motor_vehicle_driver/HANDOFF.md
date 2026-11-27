# C378809 / NRS 484B.477(1)(a) CPU handoff

Status: **partial**. Three exact source-gated Native constructions are selected for CPU preparation and pass current-runtime offline checks. Public compatibility, recorded-only Core/video processing, semantic and independent delivery proofs remain incomplete. No physical or legal acceptance is claimed.

## Exact law and cell

- Frozen assignment SHA-256 `9403da615d8a0634526601f205cf715edf4e9cdfd99d3ea8f9fb410534c0a736`; witnesses SHA-256 `1900c0e356518fc1aa1a92ae97259c2fe7c464676b439adfd37d1a918c9d04b2`. No accepted recordings are listed.
- Fixed cell: `business_district_alley / park / alley_entrance`, actor `motor_vehicle_driver`. Exact text prohibits stopping, standing or parking within a business-district alley unless local ordinance provides otherwise or the stop is for expeditious loading/unloading of goods. Commercial vehicle status is contextual, not an element of this exact text.
- Business district, statutory alley/public way and local ordinance status require original source review. Scripted prop motion and a door cue cannot prove actual goods transfer. The measured dwell reducer uses a 0.05 m/s sensor-rest tolerance only; it does not define “expeditious.” No expected legal labels are assigned.

## Current selected CPU checkpoint (2026-11-26)

- Current runtime verification and preflight passed. `native/selected_plan.py` defines three exact requests at the frozen cell: observed goods-motion attempt, no-goods request, and goods-motion followed by idle. `compare()` enforces fixed surveyed site, park point, actor context, and ordinance source; it never returns a legal result or an expeditiousness threshold. Negative tests reject absent ordinance/goods sources and changed comparison parking position.
- `native/selected_runner.py` uses the current `runtime/scenario_pipeline` import path supplied by runtime execution, 600 original 20 Hz frame identities, four pinned camera views, lossless per-view FFV1, and synchronized four-view primary composition. It requests source-aligned goods-prop motion only in probes 01/03 and records that this does not verify a real goods transfer. `native/selected_finalize.py` joins source-reviewed survey, full-interval independent goods review, original trace/frame map and four video hashes; diagnostic positive and missing-source/frame-join negatives pass. Its output leaves expeditiousness, physical completion and legal outcome unresolved.
- `native/build_selected.py` materializes three case-specific bundles under `native-selected/`. Pinned `runtime.py offline` passed for each final construction with `simulation_started: false`. Logs: `native-selected/probe_01/primary-offline.log`, `native-selected/probe_02/primary-offline.log`, `native-selected/probe_03/primary-offline.log`; their hashes are bound in `selected-draft-manifest.json` and `result.json`. These are selected CPU constructions, not delivery-ready packages.
- `case-plan.json` now has separate goods versus no-goods and goods versus post-goods-idle comparisons, exact pinned camera plan, and source-observation mapping. The local-ordinance override has no supplied authoritative finding; it remains a separate source-dependent statutory alternative. No case asserts an ordinance outcome.

## Exact remaining CPU preparation

1. Complete the selected saved finalizer's canonical Native result, channel evidence, media decode, and current Core converter contract; preserve original-source negatives. Create exact source-hashed diagnostic recipes and run `runtime.py compatibility` positive/missing-source for all selected cases.
2. Run `runtime.py process-saved` recorded-only positive/negative fixtures, semantic proposal/index checks, physical/lifecycle tests, independent delivery and controlled comparison audits. Bind final receipts to `execution-manifest.json`; retain original authority and physical review as unresolved.
3. Run `.venv-cpu/bin/python -B worker_check.py --assignment training__C378809__NRS-484B-477-1a__motor_vehicle_driver --complete --require-delivery-ready` on final bytes. Keep `result.json` partial until the entire check exits zero.

### Measured comparison and contract update

- Probe 01 requests goods-prop motion at frame 480; probe 03 requests it at frame 200. This produces different physical post-goods observation windows at fixed 600-frame duration, not a legal expeditiousness cutoff. The original videos and independent goods review must verify actual goods events.
- `native/audit_selected_comparisons.py` independently checks the three saved measurements, fixed site and ordinance source, observed goods/no-goods contrast, and measured post-goods stopped-time difference. Source-shaped positive and changed-site/changed-goods/no-difference negatives pass. It returns no legal result.
- Each `native-selected/probe_0*/measurement-contract.json` binds disposition 0 to `selected_finalize.py:measure_alley`, requiring the site survey, goods review, original trace and frame map; the negative removes `goods-review.json`. The current runtime measurement-contract validator passed all three. Current construction bytes passed the exact offline command again after goods timing and finalizer changes.
