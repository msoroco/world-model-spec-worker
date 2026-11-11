# Handoff: heldout__C152972__NRS-484B-400-5__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn where both intersecting highways are one-way, both the approach for the left turn and the left turn must be made as close as practicable to the left-hand curb or edge of the highway.

Cell C152972: one_way_to_one_way_intersection / left_turn / curb; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Both intersecting highways one-way and intended left turn at intersection.
- Compare approach body position close to left curb or edge while holding departure.
- Compare left-turn path body position close to left curb or edge while holding approach.
- No numeric legal cutoff for “as close as practicable.”

## Current checkpoint

Three cases now compare approach body distance from the source left curb and turn departure body distance from the destination left curb separately, holding the other motion fixed. `oneway_turn_geometry.py` reads original map curb lines and four-corner subject footprints; `oneway_turn_comparison_audit.py` rejects changed fixed conditions. Tests pass and reject wrong directionalities and missing turn phases. `cpu-tests.log` SHA256 is `7c6964cb69b6f1074215a67076f408fa13e887ccb22eafefe759369e4fda9d24`. The distances are engineering measurements, with no invented legal practicability cutoff.

Status remains partial. Exact Native construction, four-camera capture, finalizer integration, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C152972__NRS-484B-400-5__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C152972__NRS-484B-400-5__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C152972__NRS-484B-400-5__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.
