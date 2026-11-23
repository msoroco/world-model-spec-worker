# testing__C150979__LVMC-11-16-060__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.16.060 — The prima facie speed limit is twenty-five miles per hour on all streets and highways unless a different speed limit is posted as set forth in this Title.
Assigned branch(es): Twenty-five-mile-per-hour prima facie default without a different applicable posted limit..
Cell: C150979 (one_way_road, travel, speed_limit_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150979__LVMC-11-16-060__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable checkpoint

Exact law review kept the 25 mph prima facie rule and different applicable posted limit exception separate. `case-plan.json` now proposes same-value 25 mph sign probes at requested 20/25/30 mph and a 35 mph different-posting control at requested 30 mph, with two controlled comparisons. This cell fixes `speed_limit_sign`; a truly sign-free default would need a compatible different cell and cannot be silently claimed here. Municipal jurisdiction, Title posting rules and rebuttal remain unresolved. No accepted recordings exist.

`speed_delivery.py` validates a source-sealed municipal one-way site, complete sign inventory and governing extent, map identity and Native lane before lazy ego spawn. `control_tick` reads actual velocity to apply bounded throttle/brake. `measure` retains original 20 Hz frame joins, speed, route progress, sign passage/readback; requested speed never substitutes for observation. `compare` rejects missing or changed members, map or route. `delivery_audit.py` rejects stale Native result, posting source seals, measurement-time mismatches and missing four-camera/frame-map source claims, while explicitly leaving full decode/pixels to later independent receipts. The fixture check does not establish physical completion.

Focused command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150979__LVMC-11-16-060__motor_vehicle_driver/tests -v`; exit 0, 7 tests, log `cpu-tests.log`, SHA-256 `9f318e4a8d80a118d6403227cbc813082fcc162bf809892c163b9579ed4c3106`.

Next CPU steps: source-map/Title packet for chosen site; full executable Native sign and four-camera capture integration; per-case measurement contracts, diagnostic recipes and exact offline/positive/negative compatibility receipts; semantic proposals, manifest, candidate trigger decision and actual saved processing/audits. Retain status partial until exact strict gate passes.

Exact assignment check: `.venv-cpu/bin/python worker_check.py --assignment testing__C150979__LVMC-11-16-060__motor_vehicle_driver --complete` exit 0 (`cpu-static-check.log`). Exact strict check with `--require-delivery-ready` exit 1 at `Preparation acceptance failed: partial/missing packages remain` (`cpu-strict-check.log`), consistent with truthful partial result. Own files pass non-Git UTF-8, 2 MiB and whitespace/conflict-marker checks.
