# C276300 grade standing checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`grade_stand.py` source-gates a qualifying vehicle on a public highway with grade and curb-side geometry. It constructs ego standing, a separately routed other vehicle and responsible-person action, then requests engine, brake and front-wheel states. Its 900-frame original finalizer verifies actual standing interval, engine ignition/RPM, brake engagement/torque, wheel direction relative to curb, person distance and grade. It reserves perceptibility, unattended status and brake effectiveness as unresolved judgments.

Seven exact cases and six comparisons in `case-plan.json` cover each preparation element, person stay/depart/passenger exchange, and slope versus flat. Frozen evidence inventory has no accepted recording. The measured person distance is never treated as automatic unattended status.

## CPU proof receipts

- `case-plan.json` SHA256 `6df88e36689e040115615030325f1180f61fcef0361ed3ced16895c12cafb12a`
- `grade_stand.py` SHA256 `c8e94b66c9e05a2df41a4eb1ec5ea292a1d5e53f77b98424df15f3ff7887e32e`
- `tests/test_grade_stand.py` SHA256 `19022ff688f2eb60a5fb4709f61537b96808fa2e6c483dffd4f788d5b22b89cb`
- `cpu-tests.log` SHA256 `dcfe654164ec1f59cee5093788cd11911f84235726c6b01369f7732b904c272e`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `d71b5079c49f5e518f4506eefc3241987adda7ef18f05cec2ac4b38b146abe95`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest exit 0 (3 tests); pinned `runtime.py preflight` exit 0; scoped static `worker_check.py --assignment testing__C276300__NRS-484B-533__motor_vehicle_driver` exit 0; exact scoped strict with `--complete --require-delivery-ready` exit 1 on truthful partial. `result.json.tests` includes only successful commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case execution bundles, source-bound positive/negative compatibility, saved-only processing, semantic proposals, and independent delivery/comparison audits. Improve independent source evidence of responsible-person status and effective brake mechanics. Then rerun scoped strict. Actual CARLA preparation readback and camera visibility remain physical review after CPU readiness.
