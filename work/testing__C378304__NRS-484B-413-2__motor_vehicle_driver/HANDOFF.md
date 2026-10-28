# NRS-484B-413-2 — partition 02 handoff

Status: **partial**; readiness kind: **capability**; physical acceptance: **false**.

## Exact experiment

Cases: onset_090ft, onset_100ft, onset_110ft. Comparison: right indicator command begins 90, 100, or 110 ft before course change; measure original path and rendered lamp phases. `execution-manifest.json` binds each materialized construction to its SHA-256 and each case to a package-specific compatibility receipt. `case-plan.json` maps every legal source observation term to an acquisition channel and original evidence source.

## CPU evidence

All 3 exact cases passed pinned Core atom preflight, offline runner check, actual package analysis, native validation, mandatory-observation check, Lean adapter conversion, video render and final decode. The package unit suite passed. Logs are in `tests/`; compatibility receipts and analysis logs are in `compatibility/`. `fixture-diagnostic/` is a synthetic three-frame acquisition based only on this trial's shipped compatibility example; its straight-road geometry and video cannot establish law-specific motion or physical conditions.

## Open findings

Pinned adapter paths absent for indispensable legal observations: **sig.hand_signal**. Pinned Core sig.hand_signal path is absent; this package tests the right-indicator alternative and must measure actual lamp phase and district frontage in a native run. A legal source term is retained in the plan and native channel even where the pinned Core adapter lacks its path. Required Core atoms use only supported `kin.position`, `kin.heading` and `kin.speed` paths.

The native experiment remains executable through `runner.py` and `analyze.py`, but no CARLA run, physical acceptance or compliance verdict was performed. Verify native OpenDRIVE connector topology, actor trajectories and full bodies, all four original camera views and recording duration, calibrated environmental conditions where applicable, and public-way or device authority with source evidence before physical or legal conclusions.
