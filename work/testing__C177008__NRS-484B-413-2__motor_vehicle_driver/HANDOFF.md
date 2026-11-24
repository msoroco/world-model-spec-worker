# testing__C177008__NRS-484B-413-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.413(2) — A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.
Assigned branch(es): Business-district right-turn signaling.
Cell: C177008 (paved_road, change_lane, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU checkpoint

The full law requires continuously signaling for the last 100 ft in a business or residential district and 300 ft elsewhere, before a turn or other departure from direct course, regardless of weather. The assigned branch is business-district right-turn signaling. `case-plan.json` adds two accepted-source review candidates and five unselected controlled constructions with four isolated comparisons for lead distance, continuity, district and weather. The source cell is annotated lane change; construction must prove a physical right turn or other specified rightward course change and a sourced district classification.

`continuous_signal.py` binds original source SHA256, validates 20 Hz pose/signal samples and district provenance, finds first course-change bracket, measures original planar path distance over the last uninterrupted sole-right API signal run and applies exact 30.48 m/91.44 m statutory distance. Five synthetic CPU tests cover sufficient business signaling, interruption, other area, wrong signal and missing district source. No accepted original trace is yet reviewed.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `c7c57cde0d1c57d1558f92ac2c8b8782fc2e04dec7c350d99449522946d3f9c0` |
| `continuous_signal.py` | `6a50618aaa4986e94815d9a4d9a8b3bae68229e36bb932027bef3a46ff0f6f2e` |
| `tests/test_continuous_signal.py` | `c178841866bd42c5e2eaf00cf46d6f18bfeeae4b8c30228fe81a1bfa191e3330` |
| `preflight.log` | `90e6d9115a70db608fb92c566190ebb7ef858256d42b329258976e74eee4734d` |
| `unittest.log` | `a3f077636758e429f18703c17bbe40a2573bc178d75aa6e6a52d21db95ca0e70` |
| `static.log` | `f8c181254d86e6c1ce23cb72cb518b6dcbd394fe00c463d27bf232e0f63fdb54` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: review two accepted original traces/video; construct sourced business-district right course change and signal controller, original pose/signal capture and saved finalizer; run exact offline and positive/negative compatibility plus independent delivery/comparison audits. CARLA physical motion and camera quality follow CPU readiness.
