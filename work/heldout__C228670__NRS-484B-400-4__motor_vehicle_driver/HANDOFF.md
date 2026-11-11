# Handoff: heldout__C228670__NRS-484B-400-4__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a one-way highway onto a two-directional highway, the left turn must be made by passing to the right of the centerline of the highway being entered upon leaving the intersection, and the approach for the left turn must be made as close as practicable to the left-hand curb of the one-way highway.

Cell C228670: road / left_turn / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- One-way source highway to two-directional destination, left turn at intersection: compare measured approach body position relative to left curb with held departure.
- Compare destination body position right of entered centerline on leaving intersection with held approach.
- “As close as practicable” has no numeric legal cutoff; retain geometry, body footprints, feasible obstructions and alternative position measurements.

## Current checkpoint

No accepted recordings are supplied for this assignment. The exact text, selected branch, exceptions, timing and source observations still require a finite controlled case comparison and an executable delivery package.

The case plan reviews 0 accepted source summaries and records a source-bound gap. This assignment is partial. No physical, legal, Native or delivery readiness is claimed.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C228670__NRS-484B-400-4__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.
