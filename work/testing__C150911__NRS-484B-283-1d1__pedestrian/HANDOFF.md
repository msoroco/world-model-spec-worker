# testing__C150911__NRS-484B-283-1d1__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(d)(1) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: Whenever signals exhibiting the words “Walk,” “Don’t Walk,” “Wait” or similar symbols are in place, such signals indicate as follows: While the “Walk” indication or walking person symbol is illuminated, pedestrians facing the signal may proceed across the highway in the direction of the signal and must be given the right-of-way by the drivers of all vehicles.
Assigned branch(es): Pedestrian permission paired with a separate driver duty..
Cell: C150911 (one_way_road, travel, crosswalk); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150911__NRS-484B-283-1d1__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The assigned pedestrian permission requires an illuminated WALK/walking-person indication, pedestrian facing the signal, and crossing in its direction. Driver right-of-way duty is separate. The law names NRS 484B.287, 484B.290 and 484B.350 exceptions, which remain source-review questions. `case-plan.json` adds four unselected cases and three isolated comparisons for signal state, facing and driver yielding. No accepted recordings are in the frozen inventory.

`walk_signal_measurement.py` binds an original trace hash and records first crosswalk-entry bracket, signal state, facing, direction and distinct driver-yield observation. Five synthetic CPU tests cover WALK with absent yield, WAIT, wrong direction, missing signal state and absent entry. These tests prove measurement behavior, not physical realization or statutory exception absence.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `89ddf0a6cac525fd80098d71d406a52c824fcf211a8727a141b044071ab2ca7b` |
| `walk_signal_measurement.py` | `e2070f8b0e8e255d983293e1fc878a1b985ff2b3e2fb5c8b10d226e7104e4b82` |
| `tests/test_walk_signal_measurement.py` | `d5730111d0e467d237bc6301377c9f3142e4f59eae69ed409ffbc9f3cb2ee6c9` |
| `preflight.log` | `a5169c679459992fc59fd606d9efcac583cbf776a7d529c0c0bab6a31c9d25f0` |
| `unittest.log` | `8cfe4bc46343f91698b4d69c0abf549be8695f59e47f6db648c66a6395e74a1c` |
| `static.log` | `3f36fadd0c7fd5a27fc4774615b7dbc7e98f5d696ef4efedd918953f9cf12a3b` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back a crosswalk and actual pedestrian signal, synchronized pedestrian and vehicle trajectories; review listed exception contexts; implement selected-case source finalizer, exact positive/negative compatibility, independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
