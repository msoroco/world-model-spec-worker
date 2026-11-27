# testing__C229023__NRS-486-351-2__motorcycle_or_moped_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 486.351(2); with 486.351(3) — Except as provided in subsection 3, a person shall not drive a motorcycle, moped or trimobile abreast of or overtake or pass another vehicle within the same traffic lane. Motorcycles and mopeds may, with the consent of the drivers, be operated no more than two abreast in a single traffic lane.
Assigned branch(es): Same-lane overtaking or passing.
Cell: C229023 (road, overtake, other_vehicle); actor: motorcycle_or_moped_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__NRS-486-351-2__motorcycle_or_moped_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The law prohibits same-lane abreast riding, overtaking or passing by motorcycle/moped/trimobile except subsection 3. A separate allowance permits no more than two motorcycles or mopeds abreast with drivers consent. `case-plan.json` now defines five unselected controlled constructions and three isolated comparisons for same-lane scope, consent and count. No accepted recordings exist in the frozen inventory.

`same_lane_pass.py` binds original source SHA256, validates 20 Hz lane and longitudinal relations, distinguishes a behind-to-ahead same-lane pass from riding abreast, and retains consent and subsection 3 status separately. Five synthetic CPU tests cover same-lane pass, adjacent-lane pass, abreast without pass, missing lane identity and unsubstantiated exception status. A maneuver alone cannot prove consent.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `0d8c8d14843e685103f0be344475cb3e3360066911ce8dceb7c411798da735b6` |
| `same_lane_pass.py` | `9c6f21addc439522de08eefc58ef9d94e2177ac2672a9ef63adc06b75faa736f` |
| `tests/test_same_lane_pass.py` | `073ff8bb12fe40958b4796c08a794b5bbb22fb2007a7d2d51a9e6431c8196697` |
| `preflight.log` | `654e6f941c563de3b4c4b4aee8eb1abf2789227caf5ed99950b61fbb6665ea2b` |
| `unittest.log` | `e85f44ced0249f61534c15539794cccc56603f3c8f3fafc8e769c9be1e7c3aa4` |
| `static.log` | `2622e1eb2029b8c45defc94e1342499da5b0f731baf9e16448affd920adc1519` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

The assignment's exact law text already includes subsection 3's two-abreast allowance with driver consent. The five selected cases distinguish consent, two versus three riders, and same versus adjacent lane passage. Actual driver consent and physical applicability require independently reviewed original sources; geometry alone cannot settle them.

Current CPU work: source-gated Native construction, saved finalization, five synthetic diagnostic recipes, and physical/lifecycle proofs are implemented. The first exact primary compatibility proof passed selected measurement, missing-source rejection, Native/Core/Lean validation, and four-view decode. Remaining case and fallback compatibility, saved-only replay, independent delivery/comparison audits, and the scoped strict gate are in progress. CARLA motion and camera quality follow CPU readiness.
