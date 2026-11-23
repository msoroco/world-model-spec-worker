# training__C229398__LVMC-11-52-060__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: LVMC 11.52.060. Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

full vehicle/load/trailer projection around 15 ft. Compare only `maximum_projection_perpendicular_to_curb` (ft) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 3 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## 2026-11-23 C229398 source projection construction and CPU proof

Added `native/source_footprints.py` to convert retained per-frame vehicle, load and trailer actor poses and extents into rotated footprint vertices. It requires a complete 600-frame, 20 Hz actor inventory, unique actor identities and explicit load/trailer attachment to the vehicle. Added `native/projection_measure.py` to measure the maximum streetward vertex distance along a reviewed unit curb normal across the complete vehicle, load and trailer inventory. It verifies the reviewed curb source bytes, binds each frame to the curb calibration hash and rejects missing or extra frames. The synthetic-only flag is explicit; production mode rejects synthetic rows. Both tools leave legal and physical acceptance false.

`projection-measure-proof.json` passes the 14/15/16-foot synthetic boundaries and rejects relabeling as Native, a missing part inventory, a changed curb hash, changed curb source bytes and a missing frame. `source-footprints-proof.json` passes the raw actor conversion into those same boundary measurements, demonstrates that a farther trailer changes the maximum, and rejects wrong attachment and duplicate actor identities. Each proof uses 600 source frames (30 seconds at 20 Hz). Measurement code SHA-256 `ce8b1e3b347af4fe65ac2ff82bff8d00b3e97870b46a3eb6edfdda6e6e09c239`; converter SHA-256 `23ab0bdad3a2e8718b62f8e250423589ae4dfc0c3bbc02bc66fa36f4db81c409`; measurement proof SHA-256 `ae2d26e8e05bcc4bdd07a75b5a0a470d2ab06b9a942d28f121894707d57720f7`; converter proof SHA-256 `6496fe16816d7dfed528935462ce242b5e63404a9765b9fff2a0eb838088d881`. Pinned preflight passed (log SHA-256 `3c2768e5e7221253fc7b3c02d8f2f53c9d72b42197868ff106e2567178cb6365`); assignment static complete passed (log SHA-256 `d6923148ae12cfe5b381e377e1c56b88d07d6de95b74d75a59d2a52e6b365cc3`).

C229398 remains `partial`: the original curb source, Native vehicle/load/trailer geometry and four camera streams are unverified. Build an exact selected Native construction with primary and three distinct fallbacks for each chosen boundary case; then run pinned offline, positive/negative recipe compatibility, recorded-only saved processing, independent delivery/comparison audits, queue integration and assignment-scoped strict readiness. No original Native, physical or legal acceptance is claimed. The batch strict gate has not passed. No frozen input, runtime or batch file was edited and no Git command was run.

## 2026-11-23 draft primary Native construction and offline proof

Built source-hashed draft primary bundles for all three planned 14/15/16-foot boundary cases. The runner proposes a stationary vehicle with rigidly attached load and trailer actors, positions the assembly from the full-part footprint geometry, records 600 Native actor frames at 20 Hz, and captures four original RGB source streams. It fails if the observed projection differs from the requested setting by more than 0.5 ft. The lane-edge curb is emitted only as an unreviewed proposal; source review and physical acceptance remain required. All three exact bundles passed `.venv-cpu/bin/python runtime.py offline` (runner `--check` plus CPU tests); simulation was not started. Draft manifest SHA-256 `2bdbd03f80c8e70494afd5abb3f6e0bc51f8c40d4b8f76ef668807ac3781164d`; offline proof SHA-256 `cf36b8e214104b4995ca8c68d06593878e795110adc8d84b66a53e57cc016354`. Pinned `runtime.py preflight` passed; assignment-scoped `worker_check.py --complete` passed with the full assignment ID. The initial short-ID scoped check failed because the checker requires the full assignment ID; the corrected check passed. Status remains `partial`: these are draft CPU offline checks, with no selected-case recipe compatibility, saved-processing, fallback, independent audit, comparison, or scoped strict readiness proof.
