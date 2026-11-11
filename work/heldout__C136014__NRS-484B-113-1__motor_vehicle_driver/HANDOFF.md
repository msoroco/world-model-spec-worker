# Handoff: heldout__C136014__NRS-484B-113-1__motor_vehicle_driver

## Frozen scope

The driver of a vehicle: Shall not back the vehicle unless such movement can be made with reasonable safety and without interfering with other traffic.

Cell C136014: narrow_road / reverse / other_vehicle; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Backward vehicle motion with reasonable safety and no interference with other traffic.
- Compare controlled opposing-traffic/no-conflict conditions and interference conditions while maintaining reverse maneuver.
- Reasonable safety is a judgment phrase without a statutory numeric cutoff.

## Current checkpoint

Three planned cases compare observed reverse clearance from other traffic and other-traffic speed response independently on the narrow road. `backing.py` requests narrow-road geometry, a reverse-geared subject and approaching vehicle through an adapter, then measures original 20 Hz reverse displacement, center distance and other speed change. Tests cover creation calls and missing-source, missing-motion and changed-fixed-condition rejection; `cpu-tests.log` SHA256 is `95b24ff83addcef2f141ac5ca1a3fbe12b6f1966f607763b025ad4d67601f24e`. These engineering measurements do not decide reasonable safety or interference.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C136014__NRS-484B-113-1__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C136014__NRS-484B-113-1__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C136014__NRS-484B-113-1__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.
