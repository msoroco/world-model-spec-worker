# C158196 CPU handoff — NRS 484B.257(2) signal cell

Status: **partial**. The fixed cell is one-way-to-two-way travel with `traffic_light` control. An operative signal actually controlling ego is an express exception to subsection 2's signed-entrance duty. A head elsewhere is insufficient. Frozen accepted-evidence inventory is empty.

`signal_control.py` selects the Native head by affected ego lane, applies a state with readback and restores it. `signal_yield_exception.py` joins original signal/head and frame maps to complete ego/other bodies, signed non-through entrance context and other occupancy. Three CPU tests pass for active, Off and nongoverning states, stale frame, wrong light and Native state restoration. The within-intersection observation does not decide immediate hazard or cautious yielding.

Next CPU work: source all entrance signs, signal governance and non-through status. Construct within-intersection and approaching-hazard traffic with exact signal states; implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual state and visibility remain later checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C160013__NRS-484B-127-3__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
