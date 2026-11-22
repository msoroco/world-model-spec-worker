# testing__C101303__NRS-484B-127-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.127(1) — The driver of a vehicle shall not follow another vehicle more closely than is reasonable and prudent, having due regard for the speed of such vehicles and the traffic upon and the condition of the highway.
Assigned branch(es): Following before a lane change.
Cell: C101303 (hill_crest, change_lane, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 8. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 22. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C101303__NRS-484B-127-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

## Verified source audit

`evidence_audit.py` verifies all eight frozen accepted metadata source hashes, membership identities, target sets, original trace hashes and adapted trace presence. `tests/test_evidence_audit.py` exercises success and a missing-source rejection. Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/tests`; log: `cpu-tests.log`. Accepted adapted trace and original trace hashes are intentionally distinct; only the original trace matches reconstruction.original_trace_sha256. This audit does not prove physical or statutory coverage.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 22 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.
`tests/test_evidence_audit.py` also verifies source-hashed judgment targets are strictly below/inside/above when feasible; all 3 CPU tests pass. For native precipitation strength, the exported training maximum is 100 percent, so a strictly above value cannot be constructed within the CARLA percent domain. Two exact range keys share this endpoint; see rows 5 and 16 in `judgment-probe-plan.json`. Preserve this impossible endpoint as an explicit coverage limitation, not a fabricated target.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
