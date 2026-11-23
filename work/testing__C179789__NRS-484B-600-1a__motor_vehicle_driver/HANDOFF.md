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

## 2026-11-22 independent comparison audit checkpoint

`comparison_audit.py` implements a separate saved comparison check for the six exact `case-plan.json` pairs. It requires two distinct case-bound original condition captures and SHA-256-sealed authored setup documents, identical fixed authored conditions, exactly the declared variable change, and a matching directional change in measured original condition means. The direction follows the frozen descriptions: faster, nearer traffic, wetter surface, narrower carriageway, rain and fog. It requires the same road/lane/OpenDRIVE source except for the width construction, where a different road section may be required; the authored travel direction and observation window still must match. It rejects diagnostic condition samples, tampered setup, extra authored changes, reversed differences and a request with no observed difference. The audit leaves reasonable/proper speed legally unresolved and never claims physical acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/tests -v` passed 19 CPU tests (`cpu-tests.log`); the additional eight tests exercise all six pairs and negative rejection paths with synthetic Native-shaped samples. `.venv-cpu/bin/python runtime.py preflight`, root repository tests, `worker_check.py --updates`, and exact assignment static check passed in `.runtime-work/*-comparison.log`. These prove the audit implementation and local environment only. Exact Native scene construction, source-bound reviewed roadway/material selection, four-view capture, finalization, stage proposals, offline/compatibility/saved-processing proofs and delivery audit remain worker-owned CPU work. Do not mark ready until the exact strict assignment gate passes.

The complete-batch strict gate rerun exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c179789-comparison.log`). A non-Git scan of 3,883 returned work files found zero oversize, UTF-8, trailing-whitespace, conflict-marker or C179789 proof-log hash issues; largest file is 1,628,889 bytes and the return report is 222,280 bytes before its final note. No Git command was run.

## 2026-11-22 source-bound Native construction checkpoint

`native_scene.py` adds CARLA-lazy, exact-case actor construction. A supplied source packet must enumerate all seven case IDs and cite each numeric construction; validation rejects an omitted case, a comparison with more than its declared variable changed, reversed comparison direction, changed fixed road/station in non-width pairs, invalid weather or clearance, and a world OpenDRIVE hash mismatch. The constructor checks actual OpenDRIVE driving-lane width against the requested carriageway proxy before spawning, places the leader forward in the same lane, spawns both actors, applies Native wetness/precipitation/fog and optional wheel friction, and sets the ego's initial target velocity. It restores weather and destroys participants on failure or close. Four tests exercise every exact case and negative map, width, authored-change and cleanup paths with fake Native objects. The full focused suite now passes 24 tests in `cpu-tests.log`, whose hash is updated in `result.json`.

The packet remains a required reviewed input; the CPU fixture's citations are synthetic and do not establish source authority. Initial target velocity is not a sustained speed controller. The requested wetness and OpenDRIVE driving width are engineering proxies and do not prove road material or the full statutory width. Next CPU work: bind an actual reviewed site packet, implement sustained ego/leader controllers and 20 Hz condition/camera capture in an exact runner, complete selected finalizer and audits, semantic proposals and pinned offline/saved proofs. Keep status partial.

After this construction checkpoint, exact static assignment check exits 0 (`.runtime-work/c179789-static-scene.log`); complete-batch strict exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c179789-scene.log`). A non-Git scan of 3,885 returned files found zero oversize, UTF-8, trailing-whitespace, conflict-marker or C179789 proof-log hash issues; largest file is 1,628,889 bytes and the return report was 223,390 bytes before its final note. No Git command was run.
