# testing__C230211__LVMC-11-22-020__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.22.020 — It is unlawful for any person to drive or operate a vehicle of any kind or character in a careless or imprudent manner on any highway in the City.
Assigned branch(es): Manner of driving near a barrier.
Cell: C230211 (road, travel, barrier); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230211__LVMC-11-22-020__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The broad carelessness/imprudence rule concerns operation on a highway in the City. The assigned barrier is scene context, not an ordinance element. `case-plan.json` now has two unselected route-clearance cases and one controlled comparison. Neither route spacing nor barrier contact is treated as a legal threshold. Frozen accepted inventory lists no recording.

`barrier_route.py` requires source highway, barrier and road-bound identities. It builds a connected sampled route from before to beyond a constructed barrier rectangle, checking vehicle half-width against road edges and barrier clearance. It rejects routes that collide or leave the road. Its original-frame measurement binds driver and vehicle identities, surrounding-condition source, 20 Hz speeds and four vehicle footprint vertices, then reports barrier distances without a carelessness label. Six synthetic CPU tests cover wide/near clear routes, collision and off-road rejection, missing barrier source and original body readback.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `8e87b1804642eed6f963f7da6911e7853e5f7deae2ad863f211b30f6ee14d488` |
| `barrier_route.py` | `16b443643e00d4dbf78a45bf17fd4abdc925a71e4a6431ce182fd0d995ac2c87` |
| `tests/test_barrier_route.py` | `079160559e83689a8273cd318e676da527c7693ec154902ee9b47a7b40015733` |
| `preflight.log` | `153997c3ee4ac237dce6234c3c40cad725c921e40fbf889c243ee14ee0a665d7` |
| `unittest.log` | `284f6ee112107bdb69d018447c9b2a42b487c8e45e280336b8d6aee6ee9b8d27` |
| `static.log` | `e2441bf50304d673e933b4b9854a35894449cea14a9aa51e52291468de8dbffb` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `d3820d4d7917e6a9ec86ebde0443c857260f5b7f5a5e8e3e98011077326b6e2a` |

Pinned preflight, six focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status; failed strict remains here and in `strict.log`, outside successful `result.json.tests` receipts.

Next CPU work: bind actual source city-highway, road bounds and barrier geometry; implement exact capture/controller/finalizer bundles, source-bound positive/negative compatibility, saved-only processing, semantic proposals and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
