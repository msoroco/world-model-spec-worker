# Handoff: heldout__C179789__NRS-484B-207-2__motor_vehicle_driver

## Frozen scope

Except when overtaking and passing on the right is permitted, the driver of an overtaken vehicle shall give way to the right in favor of the overtaking vehicle upon observing the overtaking vehicle or hearing a signal. The driver of an overtaken vehicle shall not increase the speed of the vehicle until completely passed by the overtaking vehicle.

Cell C179789: paved_road / travel / other_vehicle; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Overtaken driver’s give-way-right duty after observing overtaking vehicle or hearing signal, except when passing on right is permitted.
- Separate observing and hearing activation paths; compare give-way and no-give-way under fixed overtaking context.
- Overtaken driver may not increase speed until completely passed: compare pre-completion and post-completion speed change, with measured pass completion.

## Current checkpoint

No accepted recordings are supplied for this assignment. The exact text, selected branch, exceptions, timing and source observations still require a finite controlled case comparison and an executable delivery package.

The case plan reviews 0 accepted source summaries and records a source-bound gap. This assignment is partial. No physical, legal, Native or delivery readiness is claimed.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.
