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

## 2026-11-22 continuous following measurement checkpoint

`overtake_measurements.py` now also provides `analyze_following(root)` for the below/at/above 500-foot cases. It hashes the original following history, road context and frame map; requires stable distinct qualifying truck actor IDs, body vertices consistent with declared width, one sourced lane, road identity, monotone 20 Hz frame joins, and measures every lead-rear to ego-front body gap along the sourced lane tangent. It reports each sample's raw meter/foot gap, delta from the statutory 500 feet, and a 1 mm sampled equality band that is explicitly measurement precision, not a legal threshold. One short sample defeats its all-samples-at-or-above diagnostic; between-sample behavior, conditions-permit, safe occupancy and legal outcome remain unresolved. The existing `analyze(root)` passing observation path is retained.

`case-plan.json` now names the three controlled comparisons `following_gap_boundary`, `overtaking_permission`, and `same_direction_lane_exclusion`. Five CPU tests pass (three following tests plus two passing tests); `cpu-tests.log` SHA-256 `d9d0bcfab3863e365c6eb0ef91669b26f9d598de36045a9816f477a4d6e1fa7a`. Pinned `runtime.py preflight` and this assignment's `worker_check.py --complete` pass. **Status remains partial.** Next worker-owned work: bind this measurement to exact four-camera constructions for the five selected cases, run offline/compatibility/saved proofs, three triggered fallbacks per selected case, physical probes and independent delivery/comparison audits. The absence of a completed `execution-manifest.json` is unfinished construction, not a tool or environment blocker.
