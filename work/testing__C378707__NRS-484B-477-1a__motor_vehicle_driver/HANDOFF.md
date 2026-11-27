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

## 2026-11-27 12:29 UTC: source-gated Native capture path

`alley_construction.py` now builds all six exact source-gated actor schedules from a reviewed business-district alley packet, checks source references, adjacent loading zones and ordinance provenance, and targets both surveyed approach directions. `native_acquisition.py` captures 900 same-tick original activity rows and four PNG camera streams from an injected Native operator; actual map and actor IDs are read back, frame cadence is checked, and a sealed activity history is measured without a legal conclusion. `runner.py` binds a source-hashed site and operator for later CARLA use. `audit_original_attempt.py` independently checks saved actor, map, frame, activity and camera hashes and rejects diagnostic fixtures as physical attestations. Thirteen focused tests pass, including missing-camera and corrupted-media rejection. The runner still requires a reviewed operator implementation and Core finalization; semantic proposals, full exact CPU proofs and strict gate remain to be completed.

## 2026-11-27 12:32 UTC: sealed saved sources and controlled comparisons

The capture inventory now binds hashes for the site, plan, actor inventory, activity seal, frame map and measured activity; `audit_original_attempt.py` verifies those hashes and all four 900-frame camera archives. `audit_comparisons.py` verifies the five exact pairs against retained source identities and actual observed passenger, goods, driver and ordinance histories. A source-changing negative comparator is captured separately so the check is not based on post-hoc file tampering. Fifteen focused tests pass in `cpu-focused-construction-capture-audit.log`. The package remains partial during semantic, pinned compatibility, saved-only, physical and independent delivery proofs.

## 2026-11-27 12:36 UTC: canonical semantic stages

`build_semantic.py` materializes source-grounded relevance batch/cell, an exact-law template with the goods and ordinance exceptions, four independent judgment observable proposals, frozen-cell bindings, six selected canonical cases plus a nondispatched baseline, and incomplete judgment sweeps without invented legal cutoffs. The pinned `batch_pipeline.stages.validate` checks passed every stage in `cpu-semantic-stages.log` with output root exported under `.runtime-work/c378707-semantic`. Exact constructions and compatibility still need to bind the recording description before a ready claim.
