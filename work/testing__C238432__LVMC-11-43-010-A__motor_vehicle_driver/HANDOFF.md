# C238432 roundabout circulation delivery handoff

Assignment: `testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver`. Exact law: LVMC 11.43.010(A), vehicular travel within a roundabout in a counterclockwise direction. The frozen evidence inventory contains no accepted recordings and no law-specific judgment ranges. No prior evidence is reused. Legal judgment remains unresolved.

## Selected cases and comparison

- `testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver__counterclockwise`: source-reviewed entry, ring and exit route; measure original positive signed ring arc.
- `testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver__clockwise`: same surveyed roundabout and entry; measure original negative signed ring arc.
- `roundabout_circulation_direction`: compare original observations on the same map, entry, actor class, 20 Hz, 45 s capture and four camera profile. Direction is the declared change. `comparison_audit.py` rejects changed map or absent source.

The worker constructs both exact cases in `construction.json` and `cases/clockwise/construction.json`, with a bounded controller in `runner.py`, source verification and signed-arc measurement in `direction.py`, and recorded-only finalization in `analysis.py`. Each case has a slower `fallback1` route throttle after a measured cross-track failure; it preserves the route, direction and capture conditions. `case-plan.json` records every selected requirement and the physical risk.

## CPU proof and exact gate

With `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c238432`, `TMPDIR` set to the same scratch directory and `PYTHONDONTWRITEBYTECODE=1`:

- `.venv-cpu/bin/python work/testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver/prove_compatibility.py` passed exact offline and positive/negative compatibility for both primary cases and both fallback candidates. Receipts in `cases/<direction>/proof-*` bind each construction hash and exercise the Native validator, converter, Lean decoder, renderer and full decode.
- `.venv-cpu/bin/python work/testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver/prove_saved.py` passed recorded-only processing for both cases and rejected a removed original `history.json`.
- `.venv-cpu/bin/python work/testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver/prove_physical.py` passed complete motion, wrong-direction motion and missing-history fixtures for each case. These are identified synthetic fixtures. The complete fixture also exercised capture sealing, Native exit, owner release and saved-processing order.
- `.venv-cpu/bin/python work/testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver/prove_audits.py` passed independent four-view source/video/actor audit positives and missing-source negatives for both cases, plus the controlled comparison positive and missing-map negative.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver/tests` passed four focused source/geometry/history tests.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver --complete --require-delivery-ready` passed after the receipts and camera plan were bound.

## Native takeover and remaining physical checks

`result.json.first_gpu_delivery_command` selects the counterclockwise primary exact job. `queue-proposal.json` contains both exact jobs, fallback preparation, owner release, saved-only processing and independent audits for lead integration. Before Native execution, the local operator must supply the source-hashed roundabout survey and operator module through the four `SCENARIO_ROUNDABOUT_DIRECTION_*` environment variables. The survey must identify the active OpenDRIVE map, Las Vegas jurisdiction, channelized roundabout elements and both connected routes. `runner.py` rejects a changed map or absent original actor frame. The operator owns CARLA world restoration and synchronized four-view capture/sealing; its source hash must be reviewed before dispatch.

Physical CARLA route completion, island/camera visibility, participant body coverage, actual pixels, capture duration, and final legal assessment remain unverified. CPU fixture results do not assert physical acceptance. The local operator should run `delivery_audit.py` on each completed Native attempt and `comparison_audit.py` on the pair before submitting the acceptance audit.
