# testing__C179789__NRS-484B-600-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.600(1)(a) — It is unlawful for any person to drive or operate a vehicle of any kind or character at: A rate of speed greater than is reasonable or proper, having due regard for the traffic, surface and width of the highway, the weather and other highway conditions.
Assigned branch(es): Paved-road speed and conditions.
Cell: C179789 (paved_road, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 7. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 10. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C179789__NRS-484B-600-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 10 exact law/actor ranges. These are unmeasured construction targets. 4 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-22 seven-case speed and conditions CPU checkpoint

`build_branch_plan.py` binds the six frozen review comparisons to seven unique exact case IDs, reusing the same accepted `__reference` identity while preserving each comparison's one declared authored change. `case-plan.json` retains the frozen source hash and unresolved legal judgment. It does not treat accepted metadata or review descriptions as measured speed, traffic, surface, width, rain or fog. The ten judgment-range targets in `judgment-probe-plan.json` remain unmeasured and are not legal cutoffs.

`saved_conditions.py` requires a case-bound SHA-256 seal over contiguous original 20 Hz condition samples and exact source-frame joins; it retains full histories and descriptive first/minimum/maximum/mean values. `native_conditions.py` is CARLA-lazy and reads velocity, forward leader clearance, wheel friction, Native weather and OpenDRIVE driving-lane widths from live objects at the supplied snapshot. It rejects a rear or other-lane leader, absent width, changed original bytes, broken frame/time joins and a changed map source across samples. `NativeConditionCapture` appends one sampled frame per Native tick, rejects frame gaps or actor/map changes before sealing, and closes the original source once; fake Native objects exercise this CPU path without claiming original motion. The width sums driving lanes in the source OpenDRIVE; shoulder/other roadway-edge scope and legal meaning require reviewed source evidence. No reasonable/proper speed cutoff or verdict is encoded.

Eleven focused tests pass in `cpu-tests.log`; the branch plan build log and test log hashes are bound in `result.json`. Pinned CPU preflight, three repository tests and the exact static assignment check pass. The full strict batch gate exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c179789-current.log`). C179789 remains truthful `partial`. Next worker-owned CPU work: bind the seven exact Native scenes and four-view capture, add selected measurement contracts and source-hashed diagnostic recipes, run pinned offline/positive-negative compatibility and saved processing, expand the ten source-backed judgment probes where feasible, and implement independent delivery/comparison audits. Original motion, road material and pixels remain unverified. No Git command was run.

Final exact static assignment check exits 0 (`.runtime-work/c179789-static-final.log`); the rerun full strict batch gate exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c179789-final.log`). C179789 remains partial.
