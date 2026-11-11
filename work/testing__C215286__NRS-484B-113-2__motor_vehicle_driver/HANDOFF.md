# C215286 CPU handoff — NRS 484B.113(2)

Status: **partial**. Fixed cell: residence-district reverse motion at a crosswalk. This assignment covers backing on or over a crosswalk. The frozen accepted-evidence inventory is empty.

`reverse_control.py` requests actual Native reverse control, reads it back and restores prior control. `crosswalk_reverse.py` joins original frames to source-backed crosswalk polygon and complete ego body, then measures on/over and fully-over positions while reverse is active. Three CPU tests pass for positive/negative body overlap, wrong crosswalk ID, stale frame and real control restoration. Actual motion, marked geometry and camera visibility remain unverified.

Next CPU work: source exact crosswalk and residence-district road; construct positive and stop-short reverse trajectories. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual backing and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C376646__NRS-484B-250-4__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
