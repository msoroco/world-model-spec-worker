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

## Statutory and controlled comparison audit

The refreshed `statutory-review.json` maps all six exact source branches to CPU construction and remaining original evidence. The authored stop line/crosswalk hierarchy makes the absent-reference stop alternative conditional and unselected. The frozen right-turn cell cannot claim the one-way left-turn alternative. The sibling 8c packet repeats the right-turn permission; the 8d two-cycle exception concerns motorcycle, moped, trimobile and cycle actors, outside this motor-vehicle-driver case. The green-release path and referenced paragraph (d) remain unclosed. All six branch statuses stay `unproven` for delivery. Exact statutory audit passes; review SHA-256 `e2fe274c2acdedb20711ca6169ad6d9ca4de24ae71746b9f324bec7ca4abb1db`.

`audit-synthetic-comparison.py` independently checks both 480-frame source hashes and all fixed context fields. Only motion frames 100–169 differ; the reference has a 30-frame pre-crossing halt, the contrast has zero, and both share turn entry frame 181 and 1.05 s synthetic pedestrian clearance. This is controlled **synthetic** logic, not a delivery comparison or physical causation claim. Audit log SHA-256 `f10677802be86d47b96c9d0e9483fc0003d8a74bcc98b796d0595a0753dbf285`. The exact strict v2 package, independent delivery audit, statutory closure and queue remain worker-owned work.

## Current runtime update 015 checkpoint, 2026-11-11

The older v1 package and timing claims above are historical diagnostics. Rebuilt both unselected right-turn cases and four candidates per case for the current runtime, with the four required source camera names. The work-owned finalizer derives ten channels from joined raw Native samples, body, signal, walker, geometry and frame mapping. Invented speed is explicitly tagged `synthetic_native_sample`; physical setup, behavior and completion remain false. Both 480-frame direct saved positives and the independent raw audit pass 9,600 channel joins and missing-geometry/false-speed negatives.

All **8/8** current exact offline checks, **8/8** `runtime.py compatibility` checks and **8/8** actual `runtime.py process-saved` paths pass with source-hashed recipes. The exact index SHA-256 is `2c281f4e41b9610465b3b2da5788ffd05bbe69b89efaa22eebb977c8c3bea7b7`. Independent exact audit SHA-256 is `589c35bb1580e8cea94f432b2c902fbd0a0b2c8d710f29a84f69ffdc86b64b33`; it recomputes 960 raw frame joins, confirms 30 versus zero contiguous stopped frames before front crossing, checks all source and receipt hashes, and rejects three damaged receipts. Current offline summary SHA-256 is `8eb0c3414c06ed88b0251b934eef0af1a6f2264b133ef566451397eb3e1fd977`.

The saved finalizer's key `turn_entry_frame` operationally means **first sample in the destination conflict zone**, at frame 251. Last sampled walker conflict occupancy is frame 160, yielding 4.55 s to that zone. The old synthetic controller description of frame 181 and 1.05 s refers to a different turn-start quantity and is **not** the saved-path measurement. Neither timing is original physical evidence or a legal yielding verdict.

The frozen coverage witness is conditional, medium confidence and readiness zero. `case-plan.json` now records explicit source evidence gaps: official signal and stop reference, receiving-road and extreme-right position with pedestrian/traffic precedence, green-release and statutory exception branches, and selected delivery comparison. Both cases remain unselected; no original CARLA capture or accepted equivalence receipt exists. `result.json` is truthfully `partial` with zero selected cases, candidate plans proven, comparison audits passed and accepted recordings. The assignment-scoped `worker_check.py --complete` exits 0. Next worker-owned work is original source capture/review, additional required statutory branches, selected case acceptance, independent delivery comparison and queue audit. The historical `saved-fixture-proof.py` runner remains a v1 diagnostic; the current saved proof is `run-update015-saved-raw.py` and the exact matrix above.
