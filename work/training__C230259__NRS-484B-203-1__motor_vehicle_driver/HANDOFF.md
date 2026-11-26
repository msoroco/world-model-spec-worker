# NRS 484B.203(1), C230259

The exact frozen law concerns drivers proceeding in opposite directions who pass keeping right. On a highway with width for no more than one traffic line each direction, each driver must give the other at least one-half of the paved portion as nearly as possible. The selected `witness_1` and `witness_2` hold the two-way 4 m paved road, opposing vehicle, speeds, meeting interval, 600 frames at 20 Hz, and four camera profile fixed. The subject starts at different lateral positions. The plan measures each full vehicle body relative to its own road-half boundary at the body-overlap meeting interval. The phrase “as nearly as possible” remains a source and independent judgment; no numeric legal tolerance is introduced.

## Selected CPU package

`native/build_selected.py` materializes the exact construction and two candidate plans per case. `native/runner.py`, `native/road.xodr`, `native/route.py`, `native/check.py`, `native/meeting_math.py`, `native/measure_saved.py`, and `native/finalize.py` support the two selected case IDs. `case-plan.json` names two selected cases and one isolated comparison, maps every source observation term to retained channels, and specifies the synchronized four-view 30-second capture. `construction.json`, `config.json`, `proposals/cases.json`, and `execution-manifest.json` bind the selected package to the current runtime. Synthetic 600-frame source-shaped diagnostics and six missing-source mutations remain diagnostic fixtures, not accepted Native recordings.

Current-runtime CPU evidence is under `native/proofs/`: four pinned offline passes, four positive compatibility receipts with missing-pavement-source negatives, two recorded-only processing passes, physical/lifecycle preparation receipts for both cases, semantic delivery validation, independent delivery audit positives and negatives for both cases, comparison audit positive and negative, and three unit tests. The original saved evidence must be produced by the canonical GPU delivery command in `result.json` and independently reviewed for road width, both bodies, camera visibility, longitudinal meeting, and legal interpretation. There are zero accepted recordings and no physical or legal acceptance claim in this package.

## Immediate next step

Run the assignment-scoped strict gate, then dispatch the first GPU delivery command. If the strict gate fails, restore `result.json` to partial and repair the exact finding. Record original Native source and evaluate both drivers’ measured paved-width occupancy before any legal conclusion.
