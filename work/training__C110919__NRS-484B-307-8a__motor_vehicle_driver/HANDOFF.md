# training__C110919__NRS-484B-307-8a__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.307(8)(a); with 484B.307(8)(c). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

halt before legally applicable boundary versus entry without halt; right-turn yield separately. Compare only `halt_before_nearest_boundary` (bool) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Blocker and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

## Statutory branch review continuation

`statutory-review.json` distinguishes steady-red activation, the crosswalk/marking stop reference, the absent-reference intersection boundary, continued-stop duty, the frozen right-turn exception and the left-turn alternative. It keeps the paragraph (c)/(d) cross-reference unresolved. Source identity and topic coverage are checked by `audit-statutory-review.py`; all branches remain unproven and both case drafts remain unselected. The next package needs exact signal, body, road-direction and pedestrian/traffic yield sources.

## CPU Native construction checkpoint, 2026-11-06

`native/geometry.py` authors an OpenDRIVE two-way intersection, connected extreme-right approach and right-turn lane, a stop line at y=-14 m, nearest-side crosswalk at y=-11 m, governing signal proposal, and destination pedestrian crosswalk. `native/runner.py` has a CPU-only `--check` path and an explicit owned-endpoint capture path with Native map readback, vehicle and pedestrian actors, four synchronized lossless cameras, original body/actor channels, and restoration. The runner has **not** been run against CARLA; physical signal mapping, body stop, pedestrian yield, camera pixels, and completion are unobserved.

`native/engineering-plan.json` contains primary plus three distinct fallbacks for both exact cases. Fallback 1 changes route lookahead after original Native cross-track error >0.45 m; fallback 2 changes yield clearance after original actor conflict clearance <1.0 s; fallback 3 changes overview FOV after decoded original signal/body pixel margin <40 px. `native/engineering.py` rejects metrics without a matching source hash and original-source kind.

Two saved 480-frame synthetic CPU traces exercise the stop predicate and yield timing. The reference has 30 contiguous stationary frames before front crossing at frame 132; the contrast has zero before crossing at frame 102. Both hold steady red context and a 1.05 s synthetic pedestrian clearance before turn entry. `audit-native-cpu.py` independently checks source law/cell, geometry, isolated candidate knobs, fixed pair context, saved frame continuity, positive/negative measurement behavior, and forged-source rejection. This proves authored and saved-path logic only.

`draft-execution-manifest.json` binds eight exact unselected bundles. `run-draft-offline.py` executed the pinned `runtime.py offline` command for all eight; all passed with five bundle tests each. Its current summary SHA-256 is `e810f6a431fdd234d1f785af803b3f89413a2c0ec3d4141a1a793212281a8d46`. These are offline drafts, not selected delivery packages. The later saved and portable diagnostics are described below; strict v2 selection and delivery proofs remain incomplete.

## Saved and portable diagnostics continuation

`native/finalize.py` measures source-hashed steady red, full-body stop-line crossing, contiguous stationary interval, pedestrian conflict and turn exit from joined saved samples. The 480-frame `saved-fixture-proof.py` positive/negative diagnostic passes for both cases, including four decoded source videos, immutable acquisition files, and rejection when `road_geometry.json` is removed. Its log SHA-256 is `9f48941843b9d15b2539531fbb22ed7314cbccf404726fd2edf8c2ae3d68c397`.

`run-package-probes.py` exercised all eight exact candidate bundles through the pinned **v1** software package path. Each passed saved analysis, Native result validation, mandatory recording channels, Core conversion, Lean decoder, render, and final decode; each also rejected the missing `road_geometry.json` negative. `audit-package-probes.py` independently checked all eight case/candidate identities, source hashes, positive stage lists, and exact negative outcomes. Summary SHA-256: `c8543713fac1acb7ccab7f447f925ada1d4728168bf0700cfb0317784d1d6c24`; audit log SHA-256: `0e531d6c8da543dfe3fb7b9e1d2057597e0898d9a0f703c462bb42a0667085f8`.

The rebuilt exact offline summary SHA-256 is `e810f6a431fdd234d1f785af803b3f89413a2c0ec3d4141a1a793212281a8d46`. The v1 probes are synthetic diagnostics and **do not** satisfy the strict selected v2 measurement/fixture recipe, independent delivery acceptance, statutory branch closure, controlled delivery comparison, queue, or physical CARLA/pixel checks. Status remains blocked with zero selected cases.
