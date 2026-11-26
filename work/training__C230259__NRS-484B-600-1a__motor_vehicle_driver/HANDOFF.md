# C230259 NRS 484B.600(1)(a) motor vehicle driver

Status: ready for delivery preparation after exact scoped CPU gate. Four exact primary Native cases are selected for CPU preparation; no CARLA execution, accepted recording, physical speed, or legal verdict is claimed.

## Source and comparison

The frozen source addresses a rate of speed greater than reasonable or proper with due regard for traffic, surface and width, weather and other highway conditions. The assignment is road / travel / other_vehicle. The planned engineering requests are 8, 12, 16 and 20 m/s, with the same traffic, road, weather and four-camera setup. Original measured speed remains separate from controller request and no legal cutoff is inferred. `case-plan.json` retains the source and topic hashes.

## CPU proof completed

Each exact case has an inline construction, a source-shaped 600-frame, 30-second fixture, an offline proof, physical preparation proof, and current-runtime public positive and negative compatibility receipts under `native/proofs/{8,12,16,20}/`. The selected manifest binds those construction and proof hashes. The current Lean decoder accepted the final decoded result. The root materialized bundle test passes.

For each exact case, `native/proofs/<case>/saved-processing.json` records a passing saved-only current-runtime run, 600 timestamp joins, preserved original sources and `missing_evidence: false`. A separate missing `conditions.jsonl` run for each case produced `missing_evidence: true` and a feedback receipt classifying incomplete law evidence. These synthetic source fixtures are CPU software tests and cannot prove physical realization or video adequacy. `execution-manifest.json` binds positive and negative saved-processing receipts as a draft handoff.

The six canonical semantic draft stages pass the active runtime stage validators. `proposals/build_semantic.py` now uses the selected construction's exact recording description; judgment requirements refer to measured speed, frame-joined speed conditions and the four source cameras. The qualitative statutory judgment is unresolved.

## Remaining work and limits

The four selected exact cases have CPU proofs. The source-grounded qualitative judgment sweep remains explicitly incomplete and its physical feasibility and statutory range are unresolved. Original Native CARLA execution, physical source review, independent delivered-media acceptance, and the full batch queue remain GPU handoff work. No physical speed or legal threshold is inferred from controller requests. No separate fallback is selected because the current CPU road gives 1800 m against the largest 600 m request and no original Native failure mode has yet been observed.

The exact scoped command is `.venv-cpu/bin/python worker_check.py --assignment training__C230259__NRS-484B-600-1a__motor_vehicle_driver --complete --require-delivery-ready`. It passed on 2026-11-26 with `static_checks_passed: true` and the assignment reported. No runtime, frozen input or batch file was edited.

## Independent audit update

`delivery_acceptance.py` independently checks each exact saved fixture's Native, trace, conditions, participant and camera frame joins and decodes all four source videos. All four diagnostic positives pass; each non-diagnostic attempt without a capture seal is rejected. `execution-manifest.json` binds each audit script and positive/negative log hashes. `comparison_audit.py` checks the four requested speed settings with fixed road, traffic, weather and camera source sequences. Its positive CPU comparison passes and a weather mutation is rejected; `native/proofs/comparison-audit-proof.json` binds its receipts. Neither audit asserts actual pixels reviewed or physical completion from the fixture.

The main runtime `expand` command was run on the incomplete sweep: `proposals/cases.json` now has `sweeps_expanded: true` with the sweep still `status: incomplete`; no generated sweep points were claimed. The exact execution manifest and semantic delivery validator pass structural checks, as do all four delivery acceptance contracts. A scoped partial worker check passes. The qualitative judgment sweep remains open for physical review; selected exact case CPU readiness is separately checked by the scoped strict gate.
