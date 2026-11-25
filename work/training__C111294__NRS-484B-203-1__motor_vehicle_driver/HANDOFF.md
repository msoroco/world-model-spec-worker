# NRS 484B.203(1) at C111294

Frozen cell: opposing vehicle meeting on a one-lane-each-direction road. Exact statutory source and the two proposed 0.45/0.55 footprint-fraction probes are in `case-plan.json`. Two full-train membership IDs are unreviewed; no equivalence or reuse receipt is claimed.

Built source-bound 30-second, 600-frame, four-camera meeting meter (`measure_meeting.py`) and authored two-direction OpenDRIVE road plus paired ego/oncoming requests (`meeting_scene.py`). `meeting-measurement-contract.json` maps all frozen observation terms to original map, pavement, body and motion sources. CPU proof `meeting-proof.json` distinguishes 0.45/0.55 ego right-half body fractions and passing gaps, with seven negative controls. `meeting-scene-proof.json` tests the fixed road/oncoming/camera conditions and requested lateral placement, with four negative controls. Fixture hashes and motion are invented; authored geometry has not executed in Native.

The statute requires keeping right and giving at least one-half the paved portion as nearly as possible. The body's fraction in the right half is only a measurement diagnostic; it is not the statutory allocation and no legal verdict is inferred. Original road edges, lane count, physical constraints and both vehicle bodies need independent source review. The two planned cases remain unselected.

Next: create four distinct source-preserving Native candidate constructions per selected case, run pinned offline and positive/negative compatibility, capture four source cameras/600 frames, then actual recorded-only saved processing and independent acceptance/comparison audits. Keep partial until scoped strict readiness passes.

## 2026-11-25 selected Native construction and CPU proofs

Selected exact cases `__0.45` and `__0.55` now have source-hashed Native bundles in `native/bundles/`, each with authored opposing driving lanes, two vehicle tracks, four pinned 600-frame cameras, saved-source finalization and a source-bound paved-half diagnostic. The two witness rows in review-context have descriptions but no original source receipts; no source-compliance conclusion follows from those labels. The selected right-half body fractions are engineering probes, not a legal threshold.

Both primary bundles pass current-runtime CPU offline and public compatibility. Compatibility includes saved analysis from a separately labeled synthetic source-shaped recipe, a removed `pavement-survey.json` negative, Native validation, Core conversion, Lean decoder and final video decode. Both also pass recorded-only `runtime.py process-saved` on the synthetic attempts. Retained receipts are in `native/proofs/`; the full diagnostic generated outputs remain under `.runtime-work/c111294/`. A local source meter check read 600 joined frames and measured 0.45 for the 0.45 probe. No CARLA original was acquired.

The scoped static check `worker_check.py --assignment training__C111294__NRS-484B-203-1__motor_vehicle_driver --complete` passed while `result.json` remains partial. Complete the semantic stage proposals, fallback construction/proofs, independent comparison and delivery audits, physical preparation, execution manifest, and original-source review gates before any ready transition. Re-run both exact scoped strict checks only after all proof receipts are bound.

A 600-frame selected request comparison audit now passes and rejects a tampered oncoming trajectory; see `native/proofs/selected_pair_request_audit.json`. This proves request isolation only and does not claim original physical realization.

Both exact cases have one predeclared `fallback1` construction, triggered only by original primary spawn failure or road-surface overlap. It changes only initial spawn height from 1.5 m to 1.8 m. Each fallback passes current-runtime CPU offline and public positive/negative compatibility; receipts are in `native/proofs/`. No Native candidate was selected from a simulator observation.

Physical preparation now tests complete progress, incomplete progress, missing source, and the Native-exit/owner-release ordering for both selected primaries. `delivery_audit.py` independently rejects synthetic provenance and requires an original sealed acquisition, source review, pixel/law review, 600 time-joined frames, four sources, Core trace, and decoded video. Its positive predicate self-test and synthetic-source negative pass for both cases. These CPU fixtures never claim original physical success or legal compliance.

## 2026-11-25 three-case delivery preparation

Selected `__0.45`, `__0.55`, and `__1.00` are controlled 600-frame opposing-meeting requests. The first two are graded body-footprint diagnostics. `__1.00` keeps the ego body wholly in the authored right paved half and is a geometric yielding reference. Source-shaped saved readback measures right-side passing in all three and minimum paved-width fractions available to the oncoming driver of 0.3625, 0.3875, and 0.5000 respectively; fractions available to ego are 0.6875 in all three. These are synthetic CPU diagnostics. Original paved-edge, pixel, constraint, and as-nearly-as-possible review is still required; legal compliance is unassessed. The accepted membership records are not claimed as reusable because source-hashed equivalence is unavailable.

All three primary and fallback1 exact constructions pass pinned offline and positive/negative compatibility; all three primaries pass recorded-only saved processing and complete/incomplete/missing physical CPU outcome fixtures with lifecycle order. Each has positive and negative independent delivery acceptance predicate tests. `native/audit_three.py` checks all 600 request rows for a single controlled lateral difference and checks both statutory measurement fields against the source-shaped compatibility receipts. Semantic delivery has six valid stages and three selected cases. `execution-manifest.json` binds exact constructions, receipts, source measurement contracts, physical preparation and delivery acceptance. Direct execution, semantic, delivery and compatibility validators pass.

Scoped strict readiness was attempted three times: the first found missing root construction measurement_plan, the second found legacy source-channel names, and the third found missing root tests inventory. Each was repaired and `result.json` restored to partial between attempts. The root construction now records measurement_plan, termination_rules and mechanisms; case-plan maps eight source terms to the four actual capture channels; `tests/test_selected_package.py` passes. Re-run the exact scoped strict gate on these final bytes before declaring ready.

Exact scoped strict gate passed with exit 0: `.venv-cpu/bin/python worker_check.py --assignment training__C111294__NRS-484B-203-1__motor_vehicle_driver --complete --require-delivery-ready`. The check is CPU delivery preparation, not original Native recording acceptance.

Execution manifest SHA-256: `335c73a94781d09740f3b26179af082be4daa3c8ce0cf102f0c0d9feb82f7a0f`. Semantic index SHA-256: `534775975acd54459e0286a003c7ab0f39be1135cbf17aec0614148e76b7f6d1`.

Selected primary construction SHA-256 bindings:
- `training__C111294__NRS-484B-203-1__motor_vehicle_driver__0.45`: `2849a8dcec0cddd632ca379c166b8793c5b5082f345e6be4d1a8ee7580d881da`
- `training__C111294__NRS-484B-203-1__motor_vehicle_driver__0.55`: `1c798a881c0074eae981f7d3e241772e8c4f06650a8237405c6ac84fa9eed1db`
- `training__C111294__NRS-484B-203-1__motor_vehicle_driver__1.00`: `0208ffd79df94c31447dbda207201e1b60a32d64467766d064b55e6ce13f8cb0`
