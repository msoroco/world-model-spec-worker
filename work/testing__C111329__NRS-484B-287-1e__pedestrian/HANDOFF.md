# testing__C111329__NRS-484B-287-1e__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.287(1)(e) — Except as provided in NRS 484B.290 [LVMC-11-30-140-B]: When authorized to cross diagonally, pedestrians shall cross only in accordance with the official traffic-control devices pertaining to such crossing movements.
Assigned branch(es): Authorized crossing during pedestrian travel.
Cell: C111329 (intersection, travel, traffic_control_device); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1e__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint — 2026-11-23

Exact cases in `case-plan.json`: `__permissive_whole_crossing`, `__prohibitive_whole_crossing`, and `__instruction_changes_during_crossing` (each prefixed by this assignment ID). Two comparisons keep the measured opposite-corner route and official pedestrian-diagonal device fixed while varying its observed instruction. NRS 484B.290 remains an unresolved referenced exception; no legal label or numeric clearance threshold is inferred. The frozen evidence inventory has zero accepted recordings and the conditional witness is not a physical receipt.

`diagonal_crossing.py` validates source hashes for map, corner survey, authorization, device inventory and exception review; requires an opposite-corner route and pedestrian-diagonal governing device; lazily spawns the walker and applies route control with readback/cleanup. `crossing_audit.py` checks original contiguous walker and device frames, actor identity, crossing footprint, synchronized device identity/governance/instruction and fixed-condition comparison isolation. The source packet is an interface, not a claim that the frozen cell already supplies the required site. Physical risk: map route reachability and device provenance are unverified; no fallback is claimed without an exact tested construction.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1e__pedestrian/tests -v` passed 3 tests; see `cpu-tests.log` and `result.json` SHA. `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1e__pedestrian --complete --require-delivery-ready` returned exit 1 with the expected partial/missing package acceptance error; see `strict-check.log` and its SHA in `result.json`.

Next CPU work: bind a real source-surveyed diagonal site and official pedestrian-governing device; make each exact case a runnable construction bundle with source packets, finalizer, diagnostic recipe, semantic proposals, four-camera capture and manifest; run offline and positive/negative compatibility for every case; test saved-only processing and an independent full delivery audit. Only then rerun the exact strict gate and mark ready if it passes. Actual Native motion and video visibility remain later physical checks.
