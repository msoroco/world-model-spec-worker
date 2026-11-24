# testing__C230286__NRS-484B-360-1__school_bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.360(1) — A school bus shall not exceed: A speed of 55 miles per hour when transporting pupils to and from school.
Assigned branch(es): School transportation trip beside a sidewalk.
Cell: C230286 (road, travel, sidewalk); actor: school_bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230286__NRS-484B-360-1__school_bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact statutory threshold is 55 mph during school-bus transportation of pupils to or from school. `case-plan.json` now has planned 54, 55 and 56 mph active-trip cases and a 56 mph nontransport interval, with two controlled comparisons. Frozen accepted inventory is empty; no new recording is selected by this checkpoint. The law-split witness additionally requires school-bus classification and exclusion review, driver identity, trip purpose and duration, pupil presence and count, and a physically supported route beside a sidewalk.

`bus_trip.py` builds 20 Hz bounded-acceleration speed command profiles for the three threshold probes. Its original-frame measurement binds bus and driver identity, a sourced qualifying school-bus definition branch with exclusion review, to/from-school transport context, separate pupil count and sidewalk source. It computes maximum observed speed only within frames marked as active pupil transport. Six synthetic CPU tests cover profile targets, exact 55 mph boundary, above-boundary speed, nontransport exclusion and missing source facts. Commanded speed is not realized speed.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `dab379080ed2b97906c7da2e33e8a3791bd8d88d64a8da4e0ac1501a735d15d3` |
| `bus_trip.py` | `6d57ef87786b86c3561bdf99a675923634dfaf24cd1d2af2e4684d272dc711f4` |
| `tests/test_bus_trip.py` | `b885abe9b1e61093601c4a7d99355a1cd25acb2fd7271613b429dc3fff6a565d` |
| `preflight.log` | `3cf33a6173006b63828bf5a585b63ecf6efe47e82174a9a764de1ac0dda43c8f` |
| `unittest.log` | `9cb9b76820a237f54c92300c1e39c363767bd9da4888f613da0b9ce3ac84e6cb` |
| `static.log` | `6f1719c8c6b5167e49dc25e11be7330420a79d8a21bb60bc7092b0e7e543fb32` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `cba919f0ca1bf8d6195396a00abe78ed6b0f851989fe4feb9b3532b2e936ecee` |

Pinned preflight, six focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status; failed strict remains here and in `strict.log`, outside successful `result.json.tests` receipts.

Next CPU work: source the qualifying school-bus definition and all exclusions, actual pupil-trip interval and sidewalk relationship; build exact capture/finalizer bundles, positive/negative compatibility and saved-only processing; implement independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
