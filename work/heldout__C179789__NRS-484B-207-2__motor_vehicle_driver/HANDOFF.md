# Handoff: heldout__C179789__NRS-484B-207-2__motor_vehicle_driver

## Frozen scope

Except when overtaking and passing on the right is permitted, the driver of an overtaken vehicle shall give way to the right in favor of the overtaking vehicle upon observing the overtaking vehicle or hearing a signal. The driver of an overtaken vehicle shall not increase the speed of the vehicle until completely passed by the overtaking vehicle.

Cell C179789: paved_road / travel / other_vehicle; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Overtaken driver’s give-way-right duty after observing overtaking vehicle or hearing signal, except when passing on right is permitted.
- Separate observing and hearing activation paths; compare give-way and no-give-way under fixed overtaking context.
- Overtaken driver may not increase speed until completely passed: compare pre-completion and post-completion speed change, with measured pass completion.

## Current checkpoint

Four cases now separate the rightward-yield clause, no-speed-increase-until-passed clause, and the sourced right-passing exception premise. `overtaken_response.py` measures original speed and right offset after an observed or audible notice and before pass completion. `overtaken_comparison_audit.py` checks the held actor, notice and motion conditions and rejects a missing source binding. CPU tests pass; `cpu-tests.log` SHA256 is `199c77cf3f2c75565ad845489c8a7c6f65ad386d2322ab498befeef5e815c9a1`. No legal conclusion is drawn from the measured deltas.

Status remains partial. Native passing construction, four-camera capture, finalizer integration, three fallbacks per exact case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C179789__NRS-484B-207-2__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C179789__NRS-484B-207-2__motor_vehicle_driver --complete`. The strict readiness gate still fails while this package is partial.
