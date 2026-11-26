# C228096 pedestrian curb-entry handoff

Status: CPU proof set complete for 11 selected exact cases; scoped strict gate pending. Original physical or legal completion is not claimed.

## Selected construction

The pinned semantic proposal has one neutral baseline and 11 selected exact cases. Five cases cover walk versus run, close versus far vehicle, vehicle path versus road only, and departure versus remaining at the curb. Two complete three-point judgment sweeps use departure holds of 4, 6 and 8 seconds and vehicle starts at 10, 20 and 30 meters. These are bounded engineering sampling requests, not legal cutoffs or original realized measurements. Eight fixed-condition comparisons are selected in `case-plan.json` and `gpu-queue-proposal.json`.

`curb_entry.py`, `reviewed_scene.py`, `sweep_construction.py`, `native_adapter.py`, `runner.py`, `analysis.py`, `process_recorded_only.py`, `delivery_audit.py` and `comparison_audit.py` implement source-gated original curb/path geometry, timed pedestrian and driver-controlled vehicle motion, 900 synchronized frames, four Native cameras, saved-only finalization and independent source/video/comparison checks. `construction.json`, eleven `cases/*/construction.json` bundles, `config.json`, `measurement-contract.json` and the semantic index bind the exact selected scope. The canonical semantic stage validator and 13 package unit tests pass, including eight-comparison fixed-condition and rejection checks.

## Exact CPU proofs

Every one of the 11 exact cases has current pinned offline, positive and negative compatibility, recorded-only saved processing, three synthetic physical outcomes and lifecycle, and delivery positive and negative CPU proofs. `execution-manifest.json` binds these current receipts; `proof-summary.json` indexes their hashes. The queue proposal contains 11 exact job rows and eight comparison commands, with shell syntax checked. The five selected CPU validator families passed in the preceding in-memory diagnostic invocation; the current exact-case invocation and scoped strict gate are pending. No original recording or legal finding is asserted by synthetic proofs.

The assignment gate is `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__NRS-484B-283-1b__pedestrian --complete --require-delivery-ready`. Use `SCENARIO_PIPELINE_OUTPUT_ROOT` and `TMPDIR` under `.runtime-work/` for direct pipeline imports or temporary artifacts.

## Original source and review limits

Frozen evidence has no accepted original recording, and frozen judgment range inventory has no exact C228096/pedestrian range. Original reviewed curb/path site, OpenDRIVE, actor and driver packet, released Native four-camera attempts, actual motion/separation, physical feasibility, suddenness, yield opportunity and cited NRS 484B.287/.290/.350 exceptions require independent review. The source observation term list is empty in the frozen input, so `case-plan.json` has an empty source observation mapping. Capture channels still name the original motion, geometry, driver, synchronized views, actual departure time and vehicle separation.

## Stable selected artifacts

- Execution manifest SHA-256: `ab89a419c484e19ec802d6ad7900bb2f143601028b0bdb07be86c4e4ac348cdf`.
- Queue proposal SHA-256: `17f9c222be9ef995e2e0677c3444f6cef88b92f281d442aebc97c6d6119a5d48`.
- Semantic index SHA-256: `4b0324801be8e8c3c61432cc7165bd6499f5821cff14ded4fb831bff741aa0cf`.
