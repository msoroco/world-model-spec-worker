# C125745 CPU handoff — NRS 484B.250(2)

Status: **partial**. The frozen branch measures entry timing at a median-opening crossing in a stop-sign cell. The witness relocates this device comparison from C125714. The exact law excludes intersections controlled by official traffic-control devices except as provided in subsection 4, so near-time entry at an official stop sign is an observation, not a violation finding. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` names ego-left/right and close/separated entry-time cases plus opposite-direction left-turn exception context. `stop_sign_control.py` selects a Native stop sign whose trigger contains the ego approach point. `simultaneous_entries.py` requires a source-declared shared median crossing, two different highways, complete original-frame vehicle bodies and sign identity. It reports body entry times and spatial right-side geometry while leaving “approximately,” official-device status, legal yield and subsection-4 questions unresolved. Three CPU tests pass in `cpu-tests.log`, exercising trigger selection, side geometry and wrong-sign/stale-frame rejection.

Next CPU work: source a real statutory crossing through the opening, official sign status and all entrance obligations; construct two routes and stop/yield controllers; capture four named raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual sign, crossing, body timing and visibility remain later source/CARLA checks; the listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C125763__NRS-484B-250-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
