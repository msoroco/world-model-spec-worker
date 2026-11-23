# testing__C179789__LVMC-11-12-070-B__motor_vehicle_driver

Status: partial CPU construction checkpoint. Exact static check passes; exact strict delivery check fails because this package is truthfully partial. No recording, physical visibility, subsection A satisfaction, or legal verdict is claimed.

## Frozen scope and source review

LVMC 11.12.070(B): “Said driver having so yielded may proceed and the drivers of all other vehicles approaching the intersection on the through highway shall yield right-of-way to the vehicle about to enter or cross the through highway.” Ego is the approaching through-highway motor vehicle driver at C179789 (paved road, travel, other vehicle). The frozen accepted-recording inventory is empty. The single frozen conditional witness requires municipal jurisdiction, designation/authorized entrance control, explicit routes/timing and antecedent observations. The preceding subsection's satisfaction remains unresolved from this export; a stop command or speed sample does not settle it. No judgment-range entry matches this exact law and actor. Sources and hashes are in `case-plan.json`.

`case-plan.json` now has four exact cases: `__cross_yield`, `__cross_continue`, `__enter_yield`, `__enter_continue`. Each records its physical risk and reviewed-source requirements. Two controlled comparisons vary the through driver's requested response while holding the site, two vehicle roles, entrance route/timing, weather and capture contract fixed. They do not infer a legal outcome. All four require a new capture because no accepted recording exists.

## Executable CPU work

`through_highway.py` requires a source-sealed map, municipality, through-highway designation, entrance control, antecedent review, conflict geometry and distinct lane routes. Its CARLA-lazy `construct` spawns both actual actors on Native lane readback and destroys the first if the second fails. `control_tick` follows a waypoint using observed pose/velocity and bounded steering/speed feedback. `measure` requires at least 400 consecutive original 20 Hz frames with both actor identities, positions/speeds, map and intersection seals, and both conflict-box traversals. It reports observed pre-entry speed and first conflict frames with legal review explicitly unresolved. `compare` checks exact pair membership and fixed map/intersection/maneuver.

`delivery_audit.py` independently checks sealed Native result and jurisdiction/designation/control/antecedent source files, complete original frame/time join, both measured actor histories, four full camera decodes and physical-completion receipt. Its comparison audit checks both saved members and fixed site/maneuver/requested difference. These are CPU fixture tests, not actual accepted recordings.

Seven tests pass: `.venv-cpu/bin/python -m unittest discover -s work/testing__C179789__LVMC-11-12-070-B__motor_vehicle_driver/tests -v`. See `cpu-tests.log` and its SHA256 in `result.json`. The exact static command `.venv-cpu/bin/python worker_check.py --assignment testing__C179789__LVMC-11-12-070-B__motor_vehicle_driver --complete` passes (`cpu-static-check.log`). The same command with `--require-delivery-ready` fails `Preparation acceptance failed: partial/missing packages remain` (`cpu-strict-check.log`).

## Next CPU work

1. Bind an actual reviewed junction/map route and author the case-specific Native runner, configuration, finalizer and all four exact construction bundles. Preserve the subsection A antecedent as an unresolved sourced review field until exact source text and conditions are reviewed.
2. Add original-stage semantic proposals and `proposals/semantic-index.json`, each selected-requirement measurement contract and diagnostic source recipe.
3. Run exact offline and positive/negative compatibility checks for each case. Add saved-only process proof and validated execution manifest with physically justified fallbacks only after source-backed triggers are defined.
4. Rerun the focused tests and exact strict check. Keep physical motion and camera verification for the later local Native run only.
