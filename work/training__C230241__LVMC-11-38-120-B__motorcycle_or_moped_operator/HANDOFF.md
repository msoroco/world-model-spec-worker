# training__C230241__LVMC-11-38-120-B__motorcycle_or_moped_operator

Status: partial. No delivery recording is selected or claimed.

## 2026-11-23 source lighting measurement checkpoint

`native/measure_lighting.py` now requires 600 joined 20 Hz source rows over 30 seconds, a covered vehicle, at least one headlamp, a rear-mounted tail lamp, UTC clock and sunset/sunrise provenance, and calibrated source distance and visibility reviews. It measures motion-dependent burning during the half-hour sunset/sunrise window or low visibility, lamp colour, and the exact 300 ft front and 500 ft rear thresholds. It reports observations only; it makes no Native, physical, or legal verdict.

`native/prove_lighting_measure.py` passes 12 synthetic diagnostic cases, including equality at both distance cutoffs, failures one foot below, lamp activation and colour negatives, clear daytime, low-visibility daytime, and missing source joins/provenance/equipment placement. Receipt `native/lighting-measurement-proof.json` SHA-256 `2e8e33786522620a6435ad678da4498d0295ca3c8bf5043b0fafe0770c59f14b`. Pinned CPU preflight exits 0 (`native/current-preflight.log`, SHA-256 `7839cbd53644df79957521e3ebd4f36b20ce37c52844d13149dbd9433e41f93d`); assignment-scoped static complete exits 0 (`native/scoped-static-complete.log`, SHA-256 `ba048e773a8ceda7d591ec83c9e3b5995fd8920d6ea3e2288944838ea5f3ecd5`). `case-plan.json` now maps each source term to its own named source fields.

Next CPU work: construct one exact selected case with a source acquisition path for the calibrated lamp-distance and 500 ft discernibility fields, all four cameras and 30-second capture, then pass exact primary offline, positive/missing-source compatibility and saved processing. Review the statutory equipment and time conditions independently before selecting the contrast and fallback candidates. No original Native source has yet been measured. Zero cases selected; no assignment strict-ready claim.

## Source review

Law: LVMC 11.38.120(B); with 11.38.120(A). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

white headlamp reach around 300 ft plus rear lamp 500 ft and timing. Compare only `headlamp_front_visibility` (ft) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.
