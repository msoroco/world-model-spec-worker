# NRS-484B-600-1a — partition 02 handoff

Status: **partial**; readiness kind: **capability**; physical acceptance: **false**.

## Exact experiment

Cases: speed_05, speed_10, speed_15, speed_20. Comparison: commanded speed 5, 10, 15, or 20 m/s with traffic and road conditions held fixed. `execution-manifest.json` binds each materialized construction to its SHA-256 and each case to a package-specific compatibility receipt. `case-plan.json` maps every legal source observation term to an acquisition channel and original evidence source.

## CPU evidence

All 4 exact cases passed pinned Core atom preflight, offline runner check, actual package analysis, native validation, mandatory-observation check, Lean adapter conversion, video render and final decode. The package unit suite passed. Logs are in `tests/`; compatibility receipts and analysis logs are in `compatibility/`. `fixture-diagnostic/` is a synthetic three-frame acquisition based only on this trial's shipped compatibility example; its straight-road geometry and video cannot establish law-specific motion or physical conditions.

## Open findings

Pinned adapter paths absent for indispensable legal observations: **env.ice_or_snow; env.visibility**. Pinned Core env.ice_or_snow and env.visibility adapter paths are absent; actual material inventory and full highway-condition observation remain unverified. A legal source term is retained in the plan and native channel even where the pinned Core adapter lacks its path. Required Core atoms use only supported `kin.position`, `kin.heading` and `kin.speed` paths.

The native experiment remains executable through `runner.py` and `analyze.py`, but no CARLA run, physical acceptance or compliance verdict was performed. Verify native OpenDRIVE connector topology, actor trajectories and full bodies, all four original camera views and recording duration, calibrated environmental conditions where applicable, and public-way or device authority with source evidence before physical or legal conclusions.
