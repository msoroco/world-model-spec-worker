# C331230 CPU handoff — NRS 484A.450(2)

Status: **partial**. The fixed cell is a two-way-to-two-way intersection with a stop sign. The exact law makes the near-side crosswalk the first stopping reference, including an unmarked crosswalk inferred from a sidewalk connection; a marked stop line applies only if no crosswalk exists. This hierarchy differs from NRS 484B.257(1). The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps marked and sidewalk-derived crosswalks, a halt before versus inside, and a stop-line-present precedence comparison. `stop_sign_control.py` selects a real Native sign whose trigger contains the approach waypoint. `crosswalk_stop_measurements.py` joins original frames to complete ego-body geometry, source-reviewed near-side crosswalk and junction polygons, approach direction and speed. It reports a sampled full halt before crosswalk entry and subsequent junction entry without a legal conclusion. Three CPU tests pass in `cpu-tests.log`, including crosswalk priority despite a stop line, sidewalk-derived geometry, inside-crosswalk negative, missing crosswalk, stale frame and wrong sign trigger.

Next CPU work: source a properly erected sign and real marked/unmarked near-side crosswalk geometry, construct exact routes and a stop controller, capture all four raw cameras and original sign/body/reference sources. Implement saved finalizer/measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual sign, crosswalk, halt, sight and camera visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C331230__NRS-484A-450-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C80909__NRS-484B-227-1__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
