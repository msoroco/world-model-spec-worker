# C158196 CPU handoff — NRS 484B.257(1)

Status: **partial**. The frozen branch label names yield-sign nearest-view, while this bound cell fixes a traffic light. The witness assigns the active-signal exception here because C158208 fixes a yield sign. This package observes whether a signal actually controls ego traffic at entry; it does not claim to cover nearest-view yield behavior. The frozen evidence inventory has zero accepted recordings.

`case-plan.json` maps an operative governing signal, a visible but non-governing light, an Off state and a no-signal-control yield reference. `signal_control.py` selects the Native signal by affected road/lane waypoints, changes state with readback, and restores it. `signal_exception_measurements.py` joins original signal/head identity and affected-lane control state to complete ego-body entry and video frames. It reports active control at entry while leaving official and legal exception status unresolved. Three CPU tests pass in `cpu-tests.log`, including Native selection/state/restore, active versus unrelated or Off signal, stale frame and wrong-light rejection.

Next CPU work: source the official signal and properly signed baseline entrance, construct both operative and non-governing control cases, actual vehicle routes, all four raw cameras and original signal/body evidence. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical head governance, visibility and motion remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C158208__NRS-484B-257-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
