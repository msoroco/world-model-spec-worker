# testing__C136559__NRS-484B-620-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.620(2) — After the establishment of a speed zone and the installation of appropriate signs to control speed, it is unlawful for any person to drive a motor vehicle upon the road and in the speed zone in excess of the speed therein authorized.
Assigned branch(es): Speed-zone occupancy on a narrow road..
Cell: C136559 (narrow_road, travel, speed_limit_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C136559__NRS-484B-620-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable CPU checkpoint

- Exact planned cases: `signed_below`, `signed_near`, `signed_above`, `outside_zone`, `sign_not_installed`, `westbound_signed`; five comparisons in `case-plan.json`. The 25 mph value is an authored signed-zone instruction for this plan, not a general statutory cutoff. Requested speed is distinct from original measured speed.
- `speed_zone.py` gates the narrow-road map, both distinct directional lanes, zone establishment order, extent, sign instruction and readback, public road boundaries, and qualifying self-propelled nonrail motor vehicle before lazy actor construction. It retains original contiguous frame/time speed, occupancy and sign histories without deciding legal compliance. Its comparison audit rejects missing original source bindings and changed fixed conditions.
- `saved_audit.py` independently checks exact identity, source seal, site hashes, and a complete 900-frame original capture; tampering and a resealed frame gap fail tests.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C136559__NRS-484B-620-2__motor_vehicle_driver/tests -v` passed 12 tests (`cpu-tests.log`). Assignment `--complete` static gate passed (`static-check.log`). The exact `--complete --require-delivery-ready` gate failed at truthful partial acceptance (`strict-check.log`). Log hashes are in `result.json`.
- Remaining CPU work: exact runtime construction/config/finalization bundles for all six cases, source-hashed diagnostic fixtures, each case's offline and positive/negative compatibility receipts, semantic stage proposals, complete manifest with post-capture and independent delivery acceptance proofs, physical-risk fallback decisions, and saved-only process testing. A map/source order and actual physical realization remain to be verified by the local operator later; this checkpoint makes no ready or legal claim.
