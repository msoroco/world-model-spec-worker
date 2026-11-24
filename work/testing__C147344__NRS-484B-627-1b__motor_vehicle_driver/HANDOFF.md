# testing__C147344__NRS-484B-627-1b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.627(1)(b) — If any driver or operator of a motor vehicle drives or operates a motor vehicle at a speed so slow as to impede the forward movement of traffic proceeding immediately behind the driver or operator, the driver or operator shall: If the highway has two or more clearly marked lanes for traffic traveling in the direction in which the driver or operator is traveling, drive in the extreme right-hand lane except when necessary to pass other slowly moving vehicles.
Assigned branch(es): Extreme-right-hand-lane duty on a one-way multilane highway..
Cell: C147344 (one_way_multilane, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147344__NRS-484B-627-1b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The conditional law requires source-backed slow operation impeding traffic immediately behind, two or more clearly marked same-direction lanes, extreme-right-lane position, and review of the exception when passing a slowly moving vehicle is necessary. `case-plan.json` now defines four unselected construction cases and three isolated comparisons for lane position, pass state and immediate-follower relation. No accepted recordings exist in the frozen inventory.

`right_lane_measurement.py` processes original 20 Hz frames for ego/rightmost lane identity, immediate follower lane relation, gap, closing speed and observed pass. It binds a SHA256 source and rejects missing lane identities or skipped samples. Closing speed is only an observation; it does not establish legal impediment, and a pass observation does not establish necessity. Five focused tests pass.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `528b8cf62ada55ca8b8283fb4deda44c842e153a71080b16eecce67c4632bc71` |
| `right_lane_measurement.py` | `c22d908def2fcf890c4c6803a4fec8d465a781fb9e34c000f8c61806c4181f0d` |
| `tests/test_right_lane_measurement.py` | `431a4e76d0e570693252c8bb72bcf4fd6daea70bf20d08a9e78cb86f5839898f` |
| `preflight.log` | `b2742a158859f9ede99b41162978e56fb8947b02d89d2ab48f944454b4db7c6d` |
| `unittest.log` | `8284edb89f1ff680163425a23a454187a667979fa2cdbf9ea28a31c7efdee3a8` |
| `static.log` | `edc0436fde98171827bcdac9065e8b83b908253d8cfd8d52fd6007bc7cf39a44` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because the package remains partial. Command bindings are in `result.json`.

Next CPU work: implement CARLA construction/controller for the four cases, source-bound finalizer and human-review evidence packet for actual impediment and passing necessity, run exact offline and positive/negative compatibility, and add independent saved delivery and comparison audits. Physical motion and camera quality remain later CARLA checks.
