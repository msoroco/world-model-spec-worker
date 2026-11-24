# testing__C230223__NRS-484B-270-4__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(4) — Except as otherwise provided in subsection 3 [NRS-484B-270-3], the driver of a motor vehicle shall not enter or proceed through an intersection while driving within a pathway or lane provided for bicycles, electric bicycles or electric scooters.
Assigned branch(es): Road-route intersection passage within a designated cycle lane.
Cell: C230223 (road, travel, cycle_lane); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230223__NRS-484B-270-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The law prohibits a motor vehicle entering or proceeding through an intersection while driving within a pathway/lane provided for bicycles, electric bicycles or electric scooters, except subsection 3. `case-plan.json` now has four unselected constructions and three isolated comparisons for cycle-lane intersection overlap, lane designation and subsection 3 review. No accepted recordings exist in the frozen inventory.

`cycle_lane_intersection.py` binds original source SHA256, validates motor-vehicle, intersection and designated-cycle-lane identities, and tests simultaneous 20 Hz body occupation of the intersection and designated cycle lane. It preserves subsection 3 status separately. Five synthetic CPU tests cover true overlap, lane ending before intersection, ordinary-lane passage, missing designation and unresolved exception. A paint mark alone does not establish source designation.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `15b169236ed034de5b23db2d6782f90350e7a493c2da5bcbaf982bf164ca0e38` |
| `cycle_lane_intersection.py` | `e368f272b2a751eac9f509f80c23d0454da19f68d70af6cc272e92b1cec70dc5` |
| `tests/test_cycle_lane_intersection.py` | `0da909e5efbd56f45809bfd65ae106e1be03cfb557d15e6e349245ae9179119f` |
| `preflight.log` | `7ee5fe7578467aa00d469f61b6bfabced089d97ceb7113d5f24c6f5ea5411342` |
| `unittest.log` | `cd1b2d5a7f2bc27c072900612e667a49275861c786b0817c1f862f2e64768e16` |
| `static.log` | `ca883a18ff02814b24d102da8ee269a293ecc2e9a87dad0e273ee93031551a41` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back actual designated cycle-lane and intersection polygons and source vehicle occupation; review subsection 3; implement saved finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.

## 2026-11-23 route construction and receipt repair

`cycle_lane_site.py` now selects a named route against source-bound intersection and designated cycle-lane polygons. It partitions each route segment at polygon boundaries, so an overlap may be established between waypoints. It rejects routes that miss the intersection or contradict the requested overlap. Six focused geometry tests include a lane ending before the intersection, an ordinary road route and a route with no interior waypoint. These fixtures exercise construction logic only; no actual source map or recording is claimed. The eleven combined CPU tests pass.

`result.json.tests` contains only successful preflight, unit and scoped-static receipts with package-relative logs, exact commands, exit code 0 and verified SHA256. The exact scoped strict check remains exit 1 on truthful partial status and is recorded only in this handoff and `strict.log`.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `d939f357ecc57665e512c9845b8eb060c316d706613062c9b74b209ec74c0a5f` |
| `cycle_lane_site.py` | `96c7e3dd03beba7a22c7027921cbce7aa92fe6262d4f98b41d8bbab73d2a14e9` |
| `tests/test_cycle_lane_site.py` | `1a5499986017b51f6b0c0c05f7430531f6b9c0d0d9bd291a9e6a2b19f0a7450c` |
| `preflight.log` | `e1bf784607ef5dad85eebb0af01619625e84b1be637bc243d58ccd1ac83b5cf7` |
| `unittest.log` | `e95ba2d69907576ecbaf34df8e5e7a00baa61b91e0ec409a71107da67b74337d` |
| `static.log` | `ca883a18ff02814b24d102da8ee269a293ecc2e9a87dad0e273ee93031551a41` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `ec3f5a55fcf1d26181131ab827c92ffed91a59da0354c9199ea0b6e85d5f1134` |

Next CPU work: bind a real source map and designation authority to exact route candidates, inspect subsection 3's authoritative exception, implement original saved acquisition and finalizer, prove each exact bundle positive and negative compatibility, then run saved-only processing and delivery/comparison audits. Actual motion and camera quality remain later GPU checks.
