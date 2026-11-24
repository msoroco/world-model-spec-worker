# testing__C182383__NRS-484B-210-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.210(3) — The driver of a vehicle shall not overtake and pass another vehicle upon the right when such movement requires driving off the paved portion of the highway.
Assigned branch(es): Right-side passing with the operative requires condition..
Cell: C182383 (paved_shoulder, overtake_right, road_edge); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C182383__NRS-484B-210-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The operative prohibition concerns a completed overtake and pass on the right when that movement **requires** driving off the paved portion. Actual travel off pavement is a separate fact from physical necessity. `case-plan.json` now defines four unselected constructions and three isolated comparisons for corridor width, actual off-pavement choice, and whether a pass occurs. No accepted recordings exist in the frozen inventory.

`right_pass_envelope.py` binds original source SHA256, validates 20 Hz vehicle/pavement lateral envelopes and longitudinal pass identity, then reports actual off-pavement body extension and a zero-clearance geometric body-fit lower bound during overlap. It does not infer a safe legal alternative from mere width. Five synthetic CPU tests include an off-pavement path with sufficient physical corridor, proving the two concepts remain separate.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `c0afc61e0d0c4f48f62dad749b9c2da55343c61870f1dc1eabe9e2736ede0fb9` |
| `right_pass_envelope.py` | `c2d226a9976b10c7b62b0e51537eb337c504f9c6a025ffee7d1bad64aa33e5b5` |
| `tests/test_right_pass_envelope.py` | `d182d89ffa2923b506f8a2685885e55cd64c1933a88ecaba400b8e2a4d212b40` |
| `preflight.log` | `dc7443eaece283c0211b26636b6d28c21fd74df486ccb90d6ce72aeae0b07f02` |
| `unittest.log` | `ac8cdb4d61c234ba14d6811a16f68a40012180952ea534d68612ea6037a2a7c1` |
| `static.log` | `1ef68097d88d2c2629b9863d19c48d52fbb0a2abd1195db2e5ec63349d0fb373` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct and read back the paved edge and controlled overtaking geometry; save original body envelopes and road-surface classification; implement case-specific finalizer, exact positive/negative compatibility and independent delivery/comparison audits, including source review of what movement requires. CARLA motion and camera quality follow CPU readiness.
