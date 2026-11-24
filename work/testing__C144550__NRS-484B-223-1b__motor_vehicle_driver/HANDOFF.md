# testing__C144550__NRS-484B-223-1b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.223(1)(b) — If a highway has two or more clearly marked lanes for traffic traveling in one direction, vehicles must: Not be moved from that lane until the driver has given the appropriate turn signal and ascertained that such movement can be made with safety.
Assigned branch(es): Both conjunctive prerequisites before lane movement..
Cell: C144550 (one_way_multilane, change_lane, lane_marking); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 3. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 2. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 2 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU checkpoint

Added six exact cases: three source-review candidates for frozen accepted IDs and three planned controlled constructions (both observations, signal absent, independent check absent). Two comparisons specify the isolated variable and fixed conditions. No capture is selected or claimed ready. The frozen signal-distance targets include an impossible negative planning target; no legal or physical cutoff is inferred.

`lane_change_timing.py` measures sole-left API onset to first >0.05 m source-lane center displacement by planar original-pose path integral, retaining the sampled departure bracket and source SHA256. It requires original driver-check readback as a separate observation; neither that readback nor surrounding traffic by itself establishes statutory ascertainment. Five focused tests cover positive and missing-signal/check cases, sample gaps and assignment identity.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `d519ccd4c29560db5d2d5fd49a41e667e92059d5ce04d0be45c8b110a6395a97` |
| `lane_change_timing.py` | `6410b14831c1a59226bcbd4a3282c2df138954112e6ada289c393cb3f723d378` |
| `tests/test_lane_change_timing.py` | `71b69eca32058b98d18aacd26e8576c8080986640297d9ae14cb7d31c9b492cc` |
| `preflight.log` | `922701fb8ee7de8a90afe4b900f648f4c1052fcb067399f0107ece0a181251eb` |
| `unittest.log` | `f2ecc91e28dee5ae71c72923031333f99af139436d429cb668e5a9b267567cf1` |
| `static.log` | `f5e364ae41c091e61a0fe5d8910bd685b82f7ed4ae980f43ff9cce974e35793d` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five focused tests exit 0; scoped static exit 0; exact scoped strict exit 1 (`Preparation acceptance failed: partial/missing packages remain`). Log command bindings and hashes are in `result.json`.

Next CPU work: implement real controlled lane-change construction and a capture-backed driver-check source; finalize original signal/lane/traffic packets with source hashes; validate case-specific positive/negative compatibility, delivery and comparison audits. Review accepted original traces/video before deciding whether any new recording is needed. CARLA physical motion and video quality follow CPU readiness.
