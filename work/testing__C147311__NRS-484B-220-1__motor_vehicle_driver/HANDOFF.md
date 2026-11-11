# C147311 CPU handoff — NRS 484B.220(1)

Status: **partial**. Fixed cell: one-way multilane, travel, direction sign. The law requires the highway to be designated and signposted for one-way traffic, then the vehicle to move only in the designated direction. Frozen accepted-evidence inventory is empty.

`native_one_way.py` inventories at least two same-signed Native driving lanes on one road; this does not prove authority designation or signs. `one_way_measurements.py` joins original frames to complete ego bodies, sourced roadway polygon and designated direction, then reports motion projections and heading. Three CPU tests pass for positive/negative direction, wrong lane, stale frame and opposing-lane selection. The synthetic tests are implementation checks, not physical/legal acceptance.

Next CPU work: source the public designation and signposting; construct the exact Native route and direction sign with both positive/negative motion. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual motion and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C147311__NRS-484B-220-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C157964__NRS-484B-257-2__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
