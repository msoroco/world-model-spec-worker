# C179819 NRS 484B.633(2) motor vehicle driver

Status: **delivery prepared**. Twelve exact cases and five controlled comparisons are selected for the paved elevated highway branch. No accepted original recording exists in the frozen evidence inventory. The 25 mph value in diagnostic fixtures is synthetic and is never treated as a statutory speed. Original Department records, structure stationing, signs, camera pixels and legal interpretation remain source gated.

## Exact cases and coverage

- `bridge_a_speed_below`, `bridge_a_speed_at`, `bridge_a_speed_above`: source declared structural maximum minus 5, at, and plus 5 mph on the A to B bridge approach.
- `bridge_b_speed_below`, `bridge_b_speed_at`, `bridge_b_speed_above`: the same three settings on the B to A approach.
- `bridge_a_sign_99ft`, `bridge_a_sign_101ft` with `bridge_a_speed_at`: 99, 100, 101 feet before end A.
- `bridge_b_sign_99ft`, `bridge_b_sign_101ft` with `bridge_b_speed_at`: 99, 100, 101 feet before end B.
- `elevated_a_speed_at`, `elevated_a_speed_above`: another elevated structure at and above its separately declared maximum.

Every ID has the assignment prefix `testing__C179819__NRS-484B-633-2__motor_vehicle_driver__`. The five comparisons are `bridge_a_speed`, `bridge_b_speed`, `bridge_a_sign_station`, `bridge_b_sign_station`, and `elevated_structure_speed`. `case-plan.json` links every selected statutory requirement to exact cases and source requirements. The canonical `proposals/semantic-index.json` validates the 100-foot sign boundary and a three point source relative speed sweep while retaining structural safety as an unresolved judgment.

## Current CPU proofs

- 24 of 24 primary and fallback offline constructions pass `runtime.py offline`.
- 24 of 24 primary and fallback compatibility proofs pass the Native validator, Core conversion, Lean validation and full synthetic video decode. Every negative source check rejects its altered packet.
- 12 of 12 recorded-only `runtime.py process-saved` runs pass with source preservation.
- 12 of 12 physical diagnostic triplets and ordered lifecycle checks pass. They are explicitly synthetic and make no original physical acceptance claim.
- 12 of 12 independent delivery protocol positive and negative checks pass. Positive checks join motion, four camera frames and fully decoded videos from synthetic protocol sources. Negative checks reject those same sources as original delivery.
- Five of five comparison protocols pass their current case seal/isolation tests and reject mutated engineering spacing.
- Eleven focused source, construction and analysis tests pass, including 900 original-frame graph joins and owner teardown. `runtime.py preflight` passes on the pinned CPU environment.
- Direct `execution_manifest.validate`, `package_compatibility.check_receipts`, `semantic_delivery.validate`, and all 12 `delivery_handoff.validate_case` calls pass against the current package.

The exact proof commands and hashes are in `execution-manifest.json`, `cpu-comparison-proofs.json`, and `result.json`. Temporary diagnostic attempts are under `.runtime-work/c179819/`.

## Local physical review after CPU preparation

The built-in `bridge_operator.py` requires a reviewed source-hashed CARLA map dossier with both approach routes, sign asset transforms and camera poses. `native_acquisition.py` joins 900 original motion, graph and four-camera frames, closes the standard Core capture before actor teardown, and preserves the acquired actor identity. The strict assignment gate passed with `result.json` marked `delivery_prepared`. Original CARLA site realization, source review, physical crossing quality and legal interpretation remain local checks after CPU preparation.
