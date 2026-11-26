# training__C385967__NRS-484B-460__motor_vehicle_driver

Status: ready after the exact scoped strict gate passed on 2026-11-26. Six exact 30-second, 600-frame, four-camera source-bound cases cover stop, stand and park under NRS 484B.460. The official 45-degree device and curb setting is fixed while requested at-rest headings are 45 or 70 degrees. Original Native execution, physical visibility, source action realization and legal acceptance remain unverified.

Exact case suffixes: `condition_a/b` (park), `stop_condition_a/b`, and `stand_condition_a/b`. Full IDs and all three fixed-condition comparisons are in `case-plan.json`. The six selected constructions and primary/fallback candidates are in `native/selected-*-construction.json` and `execution-manifest.json`.

Completed CPU proofs: six source-bound 600-frame meter positives and missing-device negatives; three 45/70 comparisons with fixed device/curb, including wrong-action rejection for stop and stand; twelve primary/fallback offline passes; twelve primary/fallback public compatibility passes; six recorded-only saved positives and missing-device feedback negatives; six semantic validations; synthetic physical triads; six independent delivery-audit positive and invalid pixel-box negative checks. The selected runtime/library Lean decoder was built under `.runtime-work/c385967-owner-decoder` for saved processing. The completed receipts and scripts are under `native/`.

Scoped strict command:

`SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c385967-owner-output TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B worker_check.py --assignment training__C385967__NRS-484B-460__motor_vehicle_driver --complete --require-delivery-ready`

The scoped strict command returned `static_checks_passed: true` for this assignment. The first GPU command in `result.json` dispatches the selected park A case; other exact IDs are in the plan and execution manifest. The CPU receipts are synthetic diagnostic mechanics, not accepted recordings or legal determinations.
