# C393262 residential bus-stop duration

Status: partial; six selected source-gated cases and three controlled comparisons are under construction. No original recording, reviewed designation, or actual duration is supplied. The frozen cell is a residential bus stop and bus driver. The exact law covers a non-tour bus operator who stands or parks at a bus stop or an origin/destination point longer than the applicable duration designated under Section 11.60.010. This cell exercises the bus-stop alternative; origin/destination alternatives require compatible separate cells. No judgment-range entry applies to this exact law and actor.

## Selected coverage and source rule

`case-plan.json` selects `park_below`, `park_at`, `park_above`, `stand_below`, `stand_at`, and `stand_above`, all under the exact assignment prefix. The below/at/above requests are `D-2 s`, `D`, and `D+2 s`, where `D` must come from the independently reviewed location-specific designation and conditions. The `D=15 s` diagnostic fixture is synthetic and cannot establish the actual legal duration. All comparisons hold site, bus/operator, designation, camera rate and capture protocol fixed. `bus_duration.py` requires source-hashed site, designation, operator identity, independent activity transitions and 900 joined Native frame rows before computing a duration difference. It returns no legal verdict; it rejects synthetic sources in original mode, missing/changed sources, interrupted stop occupancy and loading activity that needs separate interval segmentation.

The source acquisition must supply the City Traffic Engineer designation and actual applicable duration/conditions, stop boundary and residential context, non-tour bus and operator identity, and complete standing/parking interval with activity changes. Duration need not be printed on a sign. If the actual D does not fit complete below/at/above intervals plus setup within the common 45-second capture plan, the plan and CPU proofs must be rebuilt before original capture. No legal temporal tolerance or activity cutoff is invented.

`build_duration_diagnostics.py` created six source-hashed, explicitly synthetic 900-frame packets. `cpu-duration-tests.log` records positive measurements and missing/changed-source rejection. Runtime source verification and CPU preflight passed with the pinned runtime and installed tools.

## Exact remaining CPU work

Build the Native bus and four-camera operator with reviewed site and designation gates, selected constructions and measurement contracts, canonical semantic proposals, full runtime offline and positive/negative compatibility receipts, recorded-only saved processing, independent delivery and fixed-condition comparison audits, physical-risk assessment and any justified fallback. Then run `.venv-cpu/bin/python worker_check.py --assignment testing__C393262__LVMC-11-60-030-A5__bus_driver --complete --require-delivery-ready` until it passes. `result.json` remains partial until that exact gate passes.

Physical bus behavior, actual stop geometry and designation, camera visibility, full interval capture, and independent original-source review remain later Native checks. No frozen, runtime, batch, shared, or Git file was edited by this owner.
