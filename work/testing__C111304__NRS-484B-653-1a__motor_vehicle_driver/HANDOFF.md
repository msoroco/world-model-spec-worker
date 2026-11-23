# testing__C111304__NRS-484B-653-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.653(1)(a) — It is unlawful for a person to: Drive a vehicle in willful or wanton disregard of the safety of persons or property on a highway or premises to which the public has access.
Assigned branch(es): Intersection travel with person and property context.
Cell: C111304 (intersection, travel, person); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and source-audit checkpoint

Status remains partial. The frozen evidence inventory has zero accepted recordings. `case-plan.json` now names eight exact proposed cases across highway person encounter (northbound and southbound), property proximity, and public-access-premises person encounter, with five controlled comparisons. They are planned captures, not accepted evidence or Native executions. Public-access premises must have a source-hashed site; C111304 catalog metadata alone does not establish one. The willful/wanton term has no numeric worker cutoff or automatic legal label.

`encounter.py` implements source-gated map-lane and public-access checks, separate ego and crossing vehicle spawns, fixed occupant registration, property placement, route commands, failure cleanup, and original synchronized distance/speed measurement. `saved_audit.py` independently requires a hash-matched 900-frame original history, stable identities/map/site/camera context, occupancy join, and source-bound controls; it also rejects missing comparison differences and changed fixed conditions. Nine CPU tests pass, including negative branches, in `cpu-tests.log` (SHA256 `e1723f501ded87c3b9334363c16a229e0c3d5312266e62c3004f459529294b1f`).

The exact command `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` still fails with partial/missing packages; see `strict-check.log`. Next CPU work: bind a concrete source-hashed Native site and adapter; author the exact runner/manifest and selected requirement finalizer for each case; run offline and positive/negative compatibility receipts, semantic proposals, full delivery and video audit, and source-bound comparison proofs. Physical motion and four-camera pixel visibility then require local Native execution.
