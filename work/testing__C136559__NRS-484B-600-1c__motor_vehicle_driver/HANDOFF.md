# testing__C136559__NRS-484B-600-1c__motor_vehicle_driver

Status: partial CPU preparation. Scoped strict delivery check exits 1 because the package remains partial. Eight frozen accepted recordings are retained as source review candidates, not duplicated or asserted as law coverage. Seven are full-test members; `sign_not_in_view` is demo-test only. The original trace/video bytes are absent from the export, and acceptance metadata does not prove this law's observations.

## Exact law and cases

NRS 484B.600(1)(c) addresses a rate of speed greater than that posted by a public authority for the particular portion of highway being traversed. C136559 fixes narrow_road, travel, speed_limit_sign and motor_vehicle_driver. The witness requires actual narrow-road geometry and clearance, highway dedication/public access, public-authority jurisdiction, posted rate and unit, sign position, governed segment and direction, vehicle operation, and actual speed. No speed tolerance or duration requirement is added. An off-camera sign leaves the governing rate unknown without a source-backed reading assumption.

`case-plan.json` maps the eight accepted case IDs to exact source review candidates and preserves the six frozen comparisons: strict rate boundary (below/equal/above), governed portion, governed direction, authority, units, and source visibility. The last frozen review-context comparison listed only `above`; the plan pairs it explicitly with the accepted demo-test `sign_not_in_view` candidate and records this repair. No new capture is selected while original evidence sufficiency is unresolved. All cases reference the unverified-law-coverage evidence gap.

## Implemented CPU work

`speed_source_review.py` checks SHA-256-bound original Native frame map, vehicle motion, route occupancy and posted control packets. It requires at least 900 consecutive 20 Hz frames with frame/time identity; source-backed highway, narrow-road, sign, public authority and route-portion provenance; exact occupied road segment and direction; and an off-camera sign assumption where needed. It retains every actual speed sample, posted rate/unit and per-frame signed difference only when that original portion/direction is governed. Legal applicability and priority remain unresolved. `measurement-contract.json` records source and unit joins. Synthetic fixture tests cover the exact equality boundary and mph/km/h equivalence, segment/direction exclusions, non-authority posting, off-camera assumption, stale hashes and wrong frame clock. The fixtures do not establish physical acceptance.

## Proof receipts

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA-256 `59b6fe5457d3d056f0ee5a8e7b9fe6c8dbc1368944df92061499a3f44202fa5c`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/tests -v`: exit 0; `cpu-speed-tests.log` SHA-256 `7d063643024406e14ba607e5661eb7d40926885ddd1503dcb63700795290896f`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --complete`: exit 0; `cpu-static-check.log` SHA-256 `76c4fc909dad88e8d70d86772fc316d5ae7aa2cb0944adc3782b7c83791cfa64`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --complete --require-delivery-ready`: exit 1; `cpu-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

## Remaining CPU work

Integrate original source acquisition and saved finalization for each retained candidate, implement independent source and comparison audits, finish exact-case construction/controller and semantic proposals where new capture proves necessary, then provide offline, positive/negative compatibility, delivery receipts and risk/fallback assessments. Rerun the scoped strict gate before any ready status. Physical speed, sign visibility and camera quality remain original-capture review checks.
