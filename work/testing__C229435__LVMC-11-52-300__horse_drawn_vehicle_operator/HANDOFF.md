# testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator

Status: partial source-bound branch construction. No physical recording or acceptance is claimed.

Exact frozen law: LVMC 11.52.300, nighttime parking of a nonmotor vehicle longer than thirty minutes between 01:00 and 06:00. Frozen branch: nighttime parking with another vehicle present. Actor: horse_drawn_vehicle_operator. Cell: road/park/other_vehicle. The frozen evidence inventory contains zero accepted recordings; no source-backed reuse is available. Exact-law judgment range inventory is empty.

## Exact coverage and comparisons

`case-plan.json` has eight exact cases, all retaining the second vehicle and qualifying street: `night_29m59s`, `night_30m00s`, `night_30m01s`, `outside_window_30m01s`, `motor_vehicle_30m01s`, `loading_30m01s`, `boundary_01m`, and `boundary_06m`. Seven controlled comparisons isolate duration below/at/above thirty minutes, nighttime versus outside window, motor-vehicle scope, actual loading versus parking, and the two civil-time boundaries. `build_case_plan.py` rebuilds this plan from the frozen source inventory and law. `night_parking_measurement.py` measures original continuously parked body history, 20 Hz frame joins, original civil times and overlap with the local 01:00–06:00 window. It returns no legal conclusion. The exact interpretation of time-window endpoints and cross-window counting remains for independent legal review.

## Physical construction and source constraints

`night_parking_construction.py` requires source-hashed original OpenDRIVE, municipal boundary, street-status, vehicle-build and person-activity dossiers before Native construction. It validates both vehicles' street/city placement and body dimensions; it refuses to infer a qualifying horse-drawn vehicle from the actor label or ordinary car blueprint. Each 1801-second planned episode requires 36,021 original 20 Hz frames plus four synchronized camera streams and both physical body histories. The blueprint, carriage build and motive-power dossier must be source reviewed at the local physical site. No such original source packet is in this exported worker repository; the CPU implementation tests the guard with an explicitly synthetic temporary packet under `.runtime-work`, without claiming the packet describes a real site.

## CPU proof

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator/tests -p 'test*.py' -v` after setting `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work`. The retained `cpu-night-parking-tests.log` records three passing focused tests. They exercise duration/time-window boundaries, original source hash and frame/event rejection, street placement, and the 36,021-frame construction target. `.venv-cpu/bin/python worker_check.py --assignment testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator --complete` passed after the plan was expanded; rerun after this checkpoint.

## Remaining CPU work

Implement and test Native capture and guaranteed cleanup with a source-backed physical carriage/operator, four-view media, exact case bundles, saved finalizer and measurement contracts, semantic proposals, delivery/comparison auditors, positive/negative offline compatibility receipts, and saved-only processing. Add risk-based fallback for the long-duration capture only after an exact measurable trigger and same-case construction are specified. Then run `.venv-cpu/bin/python worker_check.py --assignment testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator --complete --require-delivery-ready`. Status must remain partial until this passes. Actual physical classification, motion, camera visibility, full episode duration, and local acceptance remain GPU/local review checks after CPU readiness.
