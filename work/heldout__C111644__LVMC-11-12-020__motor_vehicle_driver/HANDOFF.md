# Handoff: heldout__C111644__LVMC-11-12-020__motor_vehicle_driver

## Frozen scope

When authorized markers, buttons, or other indications are placed within an intersection indicating the course to be traveled by vehicles turning thereat, no driver of a vehicle shall disobey the direction of such indications.

Cell C111644: intersection / turn / turn_path_marking; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Authorized markers, buttons, or other indications within an intersection must specify the turn course; compare obeying and disobeying trajectories for the same indication.
- Test indication type and authorization as sourced context; do not infer authority from visual appearance alone.

## Current checkpoint

Six planned cases compare follow versus depart responses for authorized markers, buttons and other turn-course indications placed within the intersection. `turn_marking.py` requests physical indications through an adapter and measures original 20 Hz subject distance from the indicated course; its audit checks fixed intersection, subject, course and camera conditions. Tests exercise all three indication forms and reject missing authorization and motion sources; `cpu-tests.log` SHA256 is `1c444eea02d5df858919b3207b7145795959a2f7c9fa711ed3b7041a42178897`. Observed deviation does not decide legal obedience.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111644__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111644__LVMC-11-12-020__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C111644__LVMC-11-12-020__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

### 2026-11-12 source-bound Native indication placement checkpoint

`indication_native.py` now creates and reads back physical marker, button and other-indication forms through a CARLA-lazy world interface. It requires a SHA-256-bound source record with claimed authority, exact Native map name, intersection polygon, indicated course, form-specific blueprint inventory and per-object in-intersection placement. It rejects a wrong form, changed source, object outside the polygon, nonjunction Native waypoint or position readback beyond 0.05 m, and destroys any partially spawned actors on failure. The returned record explicitly sets municipal authorization and visible-pixel verification false. The fake source authority text in CPU tests is a fixture claim, not external authorization.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C111644__LVMC-11-12-020__motor_vehicle_driver/tests -v`: six tests pass, `cpu-tests.log` SHA-256 `e741f9066502454cc5e485e04fbda73153641a6a506020cfd93b35312fd9e9c0`. The adapter has not yet been connected to a six-case Native runner, controller, original four-camera recorder, source finalizer or exact proof chain. Next CPU action: wire marker-follow first through `turn_marking.construct` into an exact CARLA-lazy bundle and source-hashed saved diagnostic, run primary offline/positive-negative compatibility/saved processing, then build its compared depart case and the remaining forms with three distinct fallbacks each. Implement independent delivery and comparison audits and canonical semantic stages before the scoped strict gate. Status stays **partial**.

### 2026-11-15 exact marker-follow construction checkpoint

`runner.py`, `config.json` and `construction.json` now assemble the first exact `__marker_follow` Native attempt. The runner checks exact identity without importing CARLA, source-hashes the supplied map/authority record, places marker props with Native junction/readback checks, drives a source-based follow target with bounded 20 Hz feedback, and retains four named original camera streams, body footprints, trace/frame mappings and a source receipt. `turn_marking.py` also derives source-joined course deviation, path length, intersection occupancy and indication context from retained originals; it rejects missing cameras, changed hashes and broken joins. Follow/depart route targets are CPU-tested for both approach directions and all three indication forms. These are software constructions and fixture proofs, not physical or municipal acceptance.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C111644__LVMC-11-12-020__motor_vehicle_driver/tests -v` (10 tests, exit 0, `cpu-tests.log` SHA-256 `e5ecedb4093406884c035779553a56162193e069d60ae5db7f6595210f8367fd`), `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/heldout__C111644__LVMC-11-12-020__motor_vehicle_driver/runner.py --check` (exit 0, Native not launched), and `.venv-cpu/bin/python worker_check.py --assignment heldout__C111644__LVMC-11-12-020__motor_vehicle_driver --complete` (exit 0).

Next CPU actions: add a finalizer CLI and Native result writer for `turn_marking.py`, create source-shaped four-camera diagnostic and recipe, prove marker-follow exact offline, positive/missing-source compatibility and fresh saved processing; then build marker-depart and button/other-indication exact bundles with three distinct risk-triggered fallbacks each. Complete canonical semantic stages, physical/lifecycle and independent delivery/comparison audits, bind current receipt hashes, and run scoped strict. Keep result partial until that proof chain passes. Returned-file count at this checkpoint is 10,192/10,200; recheck before adding proof artifacts.
