# testing__C150088__LVMC-11-52-060__motor_vehicle_driver

Status: partial CPU delivery package. Five exact delivery cases and three controlled comparisons are selected; strict readiness is pending independent audit proofs.

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

## 2026-11-26 source-bound CPU progress

Five exact cases (`vehicle_below`, `vehicle_equal`, `vehicle_above`, `load_above`, `trailer_above`) and three comparisons retain the single assigned C150088 curb cell. The statutory fifteen-foot boundary is exactly 4.572 m. The 0.08 m construction/readback tolerance and parked-dwell drift allowance are engineering checks only; they do not classify equality under the law.

`execution-manifest.json` binds ten immutable constructions (five primaries and five fallback1 at a different same-curb parking station), each with an exact offline receipt and positive/negative source-bound compatibility receipt. All ten offline and ten compatibility runs passed on the current pinned runtime, exercising the bundled finalizer, Native validation, Lean decode, four-camera media, and missing original projection history rejection. `proposals/semantic-index.json` and its five stage files pass `semantic_delivery.validate`. `physical_completion.py` has three CPU outcomes and lifecycle source proofs per case. Five `runtime.py process-saved` runs passed from diagnostic attempts with original sources unchanged; these prove saved-only software behavior, not real Native capture.

Case-specific fallback triggers are in the manifest: original pixel and Native readback audits must reveal masked controlling corners, curb references, or attachment/hitch visibility before changing from the primary 15 m curb station to the 18 m same-curb station. Perpendicular targets and all linked comparison variables remain fixed. Synthetic media and fixture projection values do not establish physical visibility or legal acceptance.

The package remains partial because the independent source-bound delivery audit, its positive/negative CPU tests, and the controlled comparison audit are unfinished. Resume with these audit implementations, bind each exact case `delivery_acceptance`, run focused tests and `.venv-cpu/bin/python worker_check.py --assignment testing__C150088__LVMC-11-52-060__motor_vehicle_driver --complete --require-delivery-ready`, then have the lead independently rerun before shared queue integration. Keep scratch and temporary files under `.runtime-work/`; use `PYTHONDONTWRITEBYTECODE=1`.
