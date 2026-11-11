# C158208 CPU handoff — NRS 484B.257(1)

Status: **partial**. The selected branch is a yield-sign approach with no stop line or near-side crosswalk, requiring the nearest point where the driver can view approaching traffic on the through highway. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps slowed, stopped and unchanged-speed responses plus through traffic already inside or approaching. `yield_sign_control.py` checks an actual Native yield-sign trigger against the ego approach waypoint. `yield_measurements.py` requires source-backed absence of the higher-priority markings, original-frame visibility samples, speed and video-frame joins. It reports a nearest sampled visible point and speed without treating sampled visibility as a legal sight location or deciding immediate hazard. Four CPU tests pass in `cpu-tests.log`, including sign trigger selection, missing ray source, stale frame, marking and signal-exception rejection. The measurement was adapted from the same-law C158190 component and tested under this assignment.

Next CPU work: source a through-highway junction and properly erected yield sign, construct an actual nearest-view geometry and visibility rays, vehicle/controller responses and all four raw source cameras. Implement saved finalizer and source channels, three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical sight, sign, traffic and camera outcomes remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The full strict gate next reports missing result `testing__C178244__NRS-484B-413-2__motor_vehicle_driver` in `strict-gate.log`. It is unfinished worker preparation, not an external dependency.
