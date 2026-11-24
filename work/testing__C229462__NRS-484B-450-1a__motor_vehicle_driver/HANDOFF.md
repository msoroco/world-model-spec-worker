# testing__C229462__NRS-484B-450-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(a); with 484B.450(3) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Except as otherwise provided in subsection 3, on a sidewalk. A person may park a bicycle, an electric bicycle or an electric scooter on a sidewalk provided that the bicycle, electric bicycle or electric scooter does not impede the normal and reasonable movement of pedestrians on the sidewalk.
Assigned branch(es): Vehicle parking on a sidewalk.
Cell: C229462 (road, park, sidewalk); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229462__NRS-484B-450-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The assigned branch concerns a motor vehicle stopping, standing or parking on a sidewalk, with traffic-conflict, law, officer, device and subsection 3 exceptions requiring separate review. The bicycle/electric bicycle/electric scooter sidewalk allowance is a distinct vehicle class. `case-plan.json` adds four unselected constructions and three isolated comparisons for overlap, boundary touch and unresolved traffic necessity. No accepted recordings exist in the frozen inventory.

`sidewalk_footprint.py` binds original source SHA256, clips a convex motor-vehicle footprint against a convex sidewalk patch and reports positive intersection area, retaining each exception independently. Five synthetic CPU tests cover partial overlap, no overlap, boundary touch, nonmotorized vehicle exclusion and unresolved traffic necessity. Original sidewalk area and physical vehicle footprint still require construction/readback.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `38b0b0ec9804958f6165a9c747f5ee40ffe420b0fa94e8274c2833ffa2a8e206` |
| `sidewalk_footprint.py` | `9c9c79068144aa18acaaed8861b5a6d5c12e88d8fc2b215ea79509ef00d4b7e4` |
| `tests/test_sidewalk_footprint.py` | `968c1c9c5e86be49ee52a4c52c6e4fd531bda6ca3346b2f79646246d8d4eb4a5` |
| `preflight.log` | `340386b765210014a4df805cc941eb8d8c5207e7555148ede4a82c87fed67372` |
| `unittest.log` | `bd4bb7146638f9774e74e0299354ee3f8fafc51138784f3b4f2ea3b24d0bec48` |
| `static.log` | `78be2b2e7ac2e83af372bbec6df5df012aae0de3b5f76a28f8192a94faec5363` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back actual sidewalk area, motor vehicle footprint and stop/stand/park action; source traffic/law/officer/device/subsection 3 exceptions; implement saved finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA realization and video quality follow CPU readiness.
