# NRS 484B.280(1)(c), C230266 motor vehicle driver

Status: **partial**. The exact source text covers a pedestrian on or near a road; at or near a bus stop, bench, shelter or transit stop; boarding public transportation; in or near a marked school zone or school crossing zone; and in or near a marked or unmarked crosswalk. `case-plan.json` now has seven controlled pairs, 14 exact cases and seven comparisons. There is no accepted recording in the frozen full-train membership. The exported summary requires source review. Neither “near” nor “proper caution” has a numeric legal cutoff in the supplied law.

## Current CPU work

- `native/caution_meter.py` and `native/branch_meter.py` measure source-shaped 600-frame packets. Actual driver observation has a separate source field; visibility and requested speed do not establish observation. The seven-position branch meter passed seven positive source packets and 11 negative packets. Its proof is `native/branch-meter-proof.json`. The earlier road meter passed two positive and six negative packets in `native/caution-meter-proof.json`. These are synthetic software fixtures, not original Native conduct.
- `native/build_branch_drafts.py` generated `draft-all-branches-manifest.json` and 14 inline constructions under `native/branch-cases/`. Every construction has a 600-frame, 20 Hz, four-camera runner and exact case/config binding. Seven pairs differ only in the post-observation engineering speed request. The 18 m trigger in the caution controller is an engineering request, not a legal proximity or caution threshold.
- `native/branch_runner.py` requires a map-bound original context survey. It constructs a pedestrian in every case, surveyed stop/sign props for relevant branches, a transit vehicle and pedestrian boarding path for boarding, and a pedestrian crossing path for marked/unmarked crosswalks. A marked crosswalk additionally requires an original visible-markings source; an unmarked one requires intersection, sidewalk and crossing-limit sources. Actor geometry is not itself proof of official stop/zone designation, actual driver observation, realized movement or legal compliance.
- All 14 exact `runtime.py offline` construction checks passed against the current runtime. Their logs and SHA-256 index are in `native/branch-cases/branch-offline-index.json`. `native/prove_branch_constructions.py` passed 14 case contracts, 14 missing-source rejections and seven comparison-isolation checks; proof: `native/branch-construction-proof.json`. These are unselected constructions, not delivery-ready cases.
- CPU preflight passed with pinned Python requirements, ffmpeg and Lean. The assignment-scoped non-ready `worker_check.py --complete` passed. The result remains partial.

## Reproduce

```text
TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/nrs280-build .venv-cpu/bin/python -B work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/native/build_branch_drafts.py
TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/nrs280-branch-proof .venv-cpu/bin/python -B work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/native/prove_branch_constructions.py
TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/nrs280-check .venv-cpu/bin/python -B worker_check.py --assignment training__C230266__NRS-484B-280-1c__motor_vehicle_driver --complete
```

## Next CPU work

Finish selected case bundles: source-bound finalizer and measurement contracts; canonical semantic proposals; exact positive/missing-source compatibility receipts for all 14 primary cases; risk-assessed same-case fallback only where justified; recorded-only processing; physical/lifecycle checker fixtures; independent delivery and seven comparison audits. Then run `.venv-cpu/bin/python worker_check.py --assignment training__C230266__NRS-484B-280-1c__motor_vehicle_driver --complete --require-delivery-ready` and retain partial until it passes. On local GPU execution, source-survey the actual map, stop/sign/crossing geometry and actor class; independently review actual observation, motion and pixels. These physical checks do not excuse any remaining CPU preparation.
