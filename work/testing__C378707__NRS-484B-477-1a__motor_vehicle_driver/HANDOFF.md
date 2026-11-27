# testing__C378707__NRS-484B-477-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.477(1)(a) — Unless otherwise provided by ordinance of the local authority having jurisdiction, a person shall not: Stop, stand or park a vehicle within an alley in a business district except for the expeditious loading or unloading of goods.
Assigned branch(es): Stopping during passenger loading.
Cell: C378707 (business_district_alley, load_unload, alley_entrance); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C378707__NRS-484B-477-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 12:30 UTC: exact business-alley passenger/goods plan and source analyzer

The frozen C378707 cell is a motor vehicle loading task in a business-district alley; its selected witness is stopping during passenger loading. The exact statute exempts expeditious goods handling, subject to a local-ordinance proviso. Six case IDs now vary passenger engagement, driver departure, goods activity/interruption and reviewed ordinance while keeping cell, actor and alley fixed. Five comparisons explicitly retain fixed conditions. No numeric legal duration or stop/stand/park cutoff is asserted. `alley_activity.py` reads a sealed 900-frame, 20 Hz original-Native history, checks every frame identity and hash, and reports physical activity intervals without a legal conclusion. Six focused positive/negative tests pass (`cpu-alley-activity-tests.log`). The plan passes assignment-scoped partial `--complete`. Next CPU work: build the source-gated Native actor/door/goods runner and four-camera capture; bind selected constructions and semantic stages; run exact offline/positive-negative compatibility, saved-only, physical, independent delivery/comparison audits and strict assignment gate. The status remains partial, not an external blocker.
