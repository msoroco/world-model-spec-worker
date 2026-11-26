# training__C385967__NRS-484B-460__motor_vehicle_driver

Status: partial. Six exact 30-second, 600-frame, four-camera source-bound cases now cover stop, stand and park under NRS 484B.460. The 45-degree device/curb setting is fixed while the at-rest requested heading is 45 or 70 degrees. Original Native execution, physical activity and legal acceptance remain unverified.

Exact case suffixes: `condition_a/b` (park), `stop_condition_a/b`, and `stand_condition_a/b`. The full IDs are in `case-plan.json` and the six selected constructions in `native/selected-*-construction.json`.

Completed CPU proof: all four new source-bound meter positives and missing-device negatives passed for 600 frame/time/body/camera joins. Stop and stand independent comparisons measured [45,70] degrees, retained identical device and curb hashes, and rejected wrong-action declarations. All eight new primary/fallback offline checks passed. Canonical semantic validation selected all six cases. All six synthetic physical triads validated. Park A/B recorded-only positives and missing-device negatives passed.

In progress: public compatibility and recorded-only processing for stop/stand primary and fallback candidates; then independent delivery-audit selftests, final six-case execution manifest and scoped strict gate. Keep result partial until the strict command passes.

Scoped strict command:

`SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c385967-owner-output TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B worker_check.py --assignment training__C385967__NRS-484B-460__motor_vehicle_driver --complete --require-delivery-ready`
