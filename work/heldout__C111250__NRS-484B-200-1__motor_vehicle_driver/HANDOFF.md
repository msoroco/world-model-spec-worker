# Handoff: heldout__C111250__NRS-484B-200-1__motor_vehicle_driver

## Frozen scope

Upon all highways of sufficient width a vehicle must be driven upon the right half of the highway, except as follows: (a) When overtaking and passing another vehicle proceeding in the same direction under the laws governing such movements; (b) When the right half of the highway is closed to traffic; (c) Upon a highway divided into three lanes for traffic under the laws applicable thereon; (d) Upon a highway designated and posted for one-way traffic; or (e) When the highway is not of sufficient width.

Cell C111250: intersection / travel / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Baseline sufficient-width highway right-half travel, with measured right/left body position.
- Exception (a): lawful overtaking and passing same-direction vehicle.
- Exception (b): right half closed to traffic.
- Exception (c): three lanes for traffic under applicable law.
- Exception (d): designated and posted one-way highway.
- Exception (e): highway not of sufficient width.
- No numeric legal cutoff for sufficient width is specified.

## Current checkpoint

Twelve planned cases cover right/left body position for the base rule and each of the five textual exceptions: same-direction overtaking, right-half closure, three lanes, posted one-way and insufficient width. `road_half.py` requests physical road variants, a closure, a one-way sign or a passing vehicle through an adapter; it measures original four-corner body position relative to the road centerline. Eleven controlled comparisons isolate side or exception premise. Tests exercise feature creation and source/fixed-condition rejection; `cpu-tests.log` SHA256 is `671fdcdc279307adebfdeadaae4812ab2a16f6bb5b78fc19a79b988c12f585c2`. None of these engineered positions decides legal exception applicability.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111250__NRS-484B-200-1__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111250__NRS-484B-200-1__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C111250__NRS-484B-200-1__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.
