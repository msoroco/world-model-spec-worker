# testing__C130282__NRS-484B-220-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.220(2) — A vehicle passing around a rotary traffic island shall be driven only to the right of such island.
Assigned branch(es): Continuous right-of-island obligation during passage..
Cell: C130282 (multilane_roundabout, circulate, traffic_island); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C130282__NRS-484B-220-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 rotary-island physical-side checkpoint

The exact NRS 484B.220(2) requires a vehicle passing around a rotary traffic island to be driven only to its right. The frozen multilane-roundabout witness is conditional and expressly warns that the roundabout label alone does not prove a qualifying island. `case-plan.json` now holds four exact inner/outer-lane right/left-side targets and three comparisons. The left-side contrasts need physically supportable routes and remain unexecuted. No accepted recordings are listed.

`island_measurements.py` reopens hash-sealed original map/trace/receipt bytes and requires an independently sourced rotary-traffic-island identity and physical polygon, distinct inner/outer circulation lanes and connected routes, a motor-vehicle driver source, original eight-vertex world-space body and heading on ordered 20 Hz frames. It computes a nearest-island-boundary local side sign and full footprint overlap for every sampled passage frame. It records right-side and left/overlap frames separately, leaving between-frame continuity and legal judgment unresolved. The CLI writes replayable JSON after validation.

Eight focused CPU tests passed in `cpu-island-tests.log`, covering CLI replay, reverse heading, physical body overlap, missing island identity or route, source mutation, missing body and diagnostic rejection. Static scoped check passed in `assignment-check.log`; exact scoped strict failed on truthful partial status in `strict-gate.log`. Proof hashes are current in `result.json`. Next CPU work: bind reviewed real Native island/map geometry and four executable route/controller bundles, synchronize/audit four cameras, author finalizers and proposals, run exact offline/positive-negative compatibility and saved-only delivery/comparison audits. Actual body motion, camera visibility and between-frame side continuity await later verification.
