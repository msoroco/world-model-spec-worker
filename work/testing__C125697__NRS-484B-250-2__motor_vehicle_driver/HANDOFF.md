# C125697 CPU handoff — NRS 484B.250(2)

Status: **partial**. The selected branch measures same-crossing entry timing at a median opening with an inoperative signal. The frozen witness relocates this qualification from C125714 because its fixed control is `other_vehicle`. The exact law addresses vehicles from different highways entering at approximately the same time, the one on the left yielding to the one on the right, with official-device and opposite-direction left-turn exclusions subject to subsection 4. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps left/right approach, measured close/separated entry timing, opposite-direction left-turn and operative-signal comparisons. `signal_control.py` requests Off on every inventoried Native entrance light, reads back and restores state. `simultaneous_entries.py` joins original video frames to complete-body entry at one sourced crossing, records the absolute time difference and right-side approach geometry, and leaves “approximately,” official-device/subsection-4 and right-of-way judgments unresolved. Three CPU tests pass in `cpu-tests.log`, including right/left geometry, operative-head rejection, stale-frame rejection and Native Off/restore calls. These are diagnostic fixtures, not physical proof.

Next CPU work: source a real median-opening crossing with two different public highways and resolve separate-intersection/spacing context. Construct both vehicle routes and entry controllers, original signal/road/body capture and all four raw cameras. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical crossing, signal, body timing and camera outcomes remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C125745__NRS-484B-250-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
