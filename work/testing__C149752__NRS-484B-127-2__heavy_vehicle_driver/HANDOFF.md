# C149752 CPU handoff — NRS 484B.127(2)

Status: **partial**. This frozen binding uses the one-way-road/overtake/truck cell to cover the actual overtaking and passing permission. The original C149237 follow cell could not realize that branch. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

The exact statute applies to a truck or combination at least 80 inches wide following another such truck, calls for 500 feet of space when conditions permit, permits overtaking and passing, and excludes highways with two or more lanes available in the same direction. One-way status alone does not establish lane count. `case-plan.json` maps sustained below/at/above 500-foot spacing, a physical pass, and the two-lane exclusion. The value 500 feet is statutory; duration and `conditions permit` remain judgment issues.

`overtake_measurements.py` reads original-frame body vertices for both qualifying trucks, Native road/lane context and video frame joins. It requires ego behind the lead, positive lateral body clearance during the maneuver, and ego wholly ahead later. It reports pass frames and lane count without a legal finding. Two CPU tests pass in `cpu-tests.log`; the negative test rejects missing lateral clearance and a stale original-frame join. This is one CPU component, not a complete capture or readiness proof.

Next CPU work: source and construct a public one-way highway with an independently counted available lane, two >=80-inch trucks, sustained following gap cases and a safe physical passing route. Implement exact Native runner, four named raw camera streams, source-bound body gap/finalizer, three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Rerun affected CPU tests and bind hashes before any ready claim. Physical road/truck/motion and safe-occupancy review remain later source/CARLA checks; the construction and proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C149752__NRS-484B-127-2__heavy_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C149752__NRS-484B-127-2__heavy_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate now reports missing result `testing__C158190__NRS-484B-257-2__motor_vehicle_driver` in `strict-gate.log`. It is unfinished worker preparation, not an external dependency.
