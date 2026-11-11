# C24811 CPU handoff — NRS 484B.250(4)

Status: **partial**. The frozen branch is a blind-intersection interaction under wholly inoperative installed, uncovered vehicular signals. The witness relocates it from C24757 because this `traffic_light` cell can also represent the operative-signal comparison. `inputs/testing__C24811__NRS-484B-250-4__motor_vehicle_driver/evidence.json` has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps the marked stop-line halt, distinct earlier-stopped and already-occupying vehicles, rolling response and operative-signal contrast. `signal_control.py` selects a Native governing light for each inventoried entrance, requests Off on all, reads back, and restores prior states. Off readback is an engineering setup fact; complete physical inoperability and uncovered heads still require original source review. `occluder_construction.py` spawns a real Native actor and checks its realized planar footprint against both approach sight rays, with cleanup. `blind_signal_measurements.py` joins the original video frames to all-head signal states and three separate complete-body vehicle histories. It reports stop and entry ordering without a legal verdict.

Four CPU tests pass in `cpu-tests.log`, including actual fake Native state and spawn calls, both approach-ray geometry, a non-obstructing negative case with cleanup, operative-head rejection, and stale-frame rejection. These are software diagnostics, not physical acceptance.

Next CPU work: source a genuine blind junction, every governing installed/uncovered head, a clearly marked stop line and a safe real occluder placement; construct synchronized ego/earlier/occupant routes and stopping controllers. Add all four raw source-camera streams, original-frame source capture, saved finalizer and measurement contract. Implement three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits, and exact offline, compatibility and saved-processing proofs. Run the assignment-scoped delivery-ready gate after those proofs. Actual occlusion, head visibility, signal inoperability and motion remain later physical checks; all listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C24811__NRS-484B-250-4__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

The pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C412593__NRS-484B-413-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not a tool or external dependency.
