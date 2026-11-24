# testing__C229435__NRS-484B-450-1i__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(i) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within 50 feet of the nearest rail of a railroad.
Assigned branch(es): Parking near a railroad rail with another vehicle present..
Cell: C229435 (road, park, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229435__NRS-484B-450-1i__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The law prohibits stopping, standing or parking within 50 feet of the nearest railroad rail, subject to necessity to avoid traffic conflict or compliance with law, police direction or official traffic-control device. Another vehicle is present in the cell, but its presence does not establish an exception. `case-plan.json` now has four unselected constructions and three isolated comparisons for inside/at/outside 50 feet and unresolved traffic necessity. No accepted recordings exist in the frozen inventory.

`rail_proximity.py` binds original source SHA256, measures from all edges of the complete vehicle footprint to every nearby rail polyline, selects the nearest rail and applies exact 15.24 m threshold. It retains each exception separately as present/absent/unresolved. Five synthetic CPU tests cover near/far, nearest of two rails, footprint rather than center and missing exception context. Real railroad identity and geometry remain unproved.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `12af7f4c33b8d38242cf128201e01c6bc5a32d5ba2559ccda6d80d1fbe249263` |
| `rail_proximity.py` | `d58182175d3212154d802812d5c573ae3b8d1c7c6c1379c1c217c3643f8ebcca` |
| `tests/test_rail_proximity.py` | `5b3154375e6d15fe1aa2f0fe5c1880cf1dfb26350508f73c4f37d6de9287dc11` |
| `preflight.log` | `73a0ce007118590b8399cf1f5cff4e7092ff92a0aad84917b351a325d24c0ca7` |
| `unittest.log` | `b1691d79e8edddd5440857941b740cad179a2702c0acb3bab91e6b6d24a628d9` |
| `static.log` | `c5ae601fd9e60e9fb7784b8804178ad14b91f8e989dc12d17746eaf92f5c5a55` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back actual railroad rail and vehicle stop/stand/park configuration, source original footprint and rail polylines, review traffic/law/officer/device exception evidence; implement saved finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA realization and video quality follow CPU readiness.
