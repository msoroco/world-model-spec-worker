# testing__C150088__LVMC-11-52-060__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.060 — In no case shall any part of any vehicle, part of the load of such vehicle or trailer attached to such vehicle, project into the street more than fifteen feet measured on a line at right angles to the curb.
Assigned branch(es): complete physical projection.
Cell: C150088 (one_way_road, park, curb); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150088__LVMC-11-52-060__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The full physical projection includes any vehicle part, load part or attached trailer part. `case-plan.json` now defines five unselected cases spanning below/equal/above fifteen feet and load/trailer controlling parts, with three isolated comparisons. No accepted recordings are in the frozen inventory.

`projection_measurement.py` binds an original source hash, validates complete part outlines and curb/street-side geometry, then computes the largest perpendicular projection into the street. Fifteen feet is exactly 4.572 m. Five synthetic CPU tests cover vehicle, load, trailer completeness, curb direction and ambiguous street side. This is a geometry proof, not evidence of physical realization.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `34bc7aef90a65f3487eb1c1421d209dfcc7632c959a6ec7060c809f1fb10bb0f` |
| `projection_measurement.py` | `62762ed0e21030c65719f67d6f07845835ab5bf19e0b72d270a72fcf48981b87` |
| `tests/test_projection_measurement.py` | `2c12c0af4506bfaa250f888829dd7df2925f466524774972738d22839eb8a2c5` |
| `preflight.log` | `226c17ac1c2b7d8404d84edac85fa77170ea3e7d5f55022158154a89ba4ae7f0` |
| `unittest.log` | `1f171ab732a00e5de83833ce9c2a5559708a923870ff9bc5fc88e53d375c785d` |
| `static.log` | `e8e7ffebb446fd4a467b09ff16d18f73bbb7cb9fda43955f11973121d19bb0e5` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: build and read back parked vehicle, load and trailer configurations with actual curb geometry; save original complete outlines; implement selected-case finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA realization and visibility follow CPU readiness.
