# C158190 CPU handoff — NRS 484B.257(2)

Status: **partial**. The frozen binding assigns stop-sign governance on a one-way-to-two-way intersection to this cell because C158208 has a fixed yield sign. The exact law requires compliance with the sign before entry and continued caution/yield to non-obligated traffic within or immediately approaching the intersection; officer and signal control are express exceptions. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` names stop/occupancy, approaching-traffic, no-traffic, rolling-response and signal-exception cases. `stop_entry_measurements.py` reads original-frame speed, stop-reference and complete-body occupancy observations, a source-backed full entrance inventory and original video-frame join. It reports whether a complete stop preceded entry and whether another body occupied the junction, leaving immediate hazard, caution and legal yield unresolved. Two CPU tests pass in `cpu-tests.log`; they include active-officer and stale-frame rejection.

Next CPU work: source a non-through-highway junction and all entrance obligations, construct actual Native stop sign and two routes, implement stop controller and four raw source cameras, approaching-hazard timing source channel and saved finalizer, three distinct physical-risk fallbacks per selected case, semantic proposals and independent audits. Run exact offline, compatibility and saved-processing proofs, then assignment-scoped strict gate. Physical geometry, control, motion, visibility and judgment context remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158190__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The full strict gate now reports missing result `testing__C158208__NRS-484B-257-1__motor_vehicle_driver` in `strict-gate.log`. It is unfinished worker preparation, not an external dependency.
