# testing__C202480__NRS-484B-560-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.560(3) — When stopping is required at a railroad crossing the driver shall keep as far to the right of the highway as possible and shall not form two lanes of traffic unless the highway is marked for four or more lanes of traffic.
Assigned branch(es): Two-lanes prohibition with its marked-four-or-more-lanes qualification; retain the independent right-side duty..
Cell: C202480 (rail_crossing, cross_railway, stop_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C202480__NRS-484B-560-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 branch plan and first audit implementation

`case-plan.json` now proposes five exact delivery cases and four controlled comparisons: two marked lanes with one or two queues, four marked lanes with two queues, and rightmost versus left-of-feasible subject placement. These are plans; no physical crossing or marked lane construction is claimed. `crossing_branch_audit.py` requires six source-hashed original evidence files before classifying the two-queue context, total marked highway lane qualification and independent right-side evidence. It never returns a legal conclusion. `cpu-branch-audit.log` passes three tests including source removal and unreviewed stop/arrangement rejection.

Next: build source-grounded crossing, sign/signal authority, marked lane geometry and independently positioned vehicle queues; implement per-frame finalizer and audited comparisons, then run offline and compatibility proofs. Keep stop authority and highway boundaries unresolved until supported by reviewed source files.

Focused `.venv-cpu/bin/python worker_check.py --assignment testing__C202480__NRS-484B-560-3__motor_vehicle_driver --complete` passed; retained in `cpu-static-check.log`. Strict delivery readiness is still unclaimed.
