# testing__C213645__LVMC-11-40-140__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.40.140 — The operator of a bicycle, electric bicycle, or electric scooter within a business or residence district entering into or emerging from an alley, driveway or building shall stop such vehicle immediately prior to driving onto a sidewalk or onto the sidewalk area extending across any alleyway, driveway or building, yielding the right-of-way to any pedestrian as may be necessary to avoid collision.
Assigned branch(es): Emerging from a driveway across a sidewalk area..
Cell: C213645 (residence_district, enter_road, driveway_entrance); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C213645__LVMC-11-40-140__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The exact branch is a qualifying cycle/scooter operator emerging from a driveway in a residence district across a sidewalk area. The law requires stopping immediately before entry and yielding to pedestrians as necessary to avoid collision. `case-plan.json` now has four unselected constructions and three isolated comparisons for stop, pedestrian conflict and yield behavior. No accepted recordings exist in the frozen inventory.

`driveway_sidewalk.py` binds original source SHA256, validates qualifying vehicle and sourced district/access/sidewalk identity, brackets first sidewalk-area entry, reports last sampled pre-entry low-speed observation and pedestrian/yield observations separately. Five synthetic CPU tests cover stop, no stop, no pedestrian, nonqualifying vehicle and absent crossing. The 0.1 m/s sample threshold is an engineering readback and does not set a legal definition of a complete stop or immediate proximity.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `54202ee2aefb05767ea7087c093471c79496928a25c6983a1c2fd416da1082fa` |
| `driveway_sidewalk.py` | `976357c35797282c0da66d0a539512a9d94e0fcc60ca3aa021b8cb9905b0ecc4` |
| `tests/test_driveway_sidewalk.py` | `26a81bef89bde6cc4b11e917dec273c5e64edb18a42e8ad42e925d07fb29253d` |
| `preflight.log` | `84dc37c79402c082a4ea6991d42409b7111f3bee25632c156ee0fed1e0314a05` |
| `unittest.log` | `ec4a2be1c2b43bf78d0010a1fe487807daedfa85b757ec0fa8af0466082cda31` |
| `static.log` | `7e3fa4cd2f4e2d012cfd516b68ebfe05a00294c6ea9b9419bef87cbe3d75fd96` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back driveway sidewalk continuation, source-bound scooter stop and pedestrian conflict trajectory; implement saved finalizer with collision-necessity review, exact positive/negative compatibility and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
