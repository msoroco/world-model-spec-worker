# testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver

Status: partial executable-case checkpoint. Twelve exact cases and ten controlled comparisons are proposed; no recording has been executed or accepted.

Exact law: LVMC 11.52.130(A)(5) — No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: In front of any sidewalk elevator or chute or within a space of five feet on each side of such sidewalk elevator or chute.
Assigned branch(es): parking near sidewalk elevator.
Cell: C150153 (one_way_road, park, sidewalk_elevator); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

- `case-plan.json` now enumerates twelve elevator cases: frontage park/stop/stand, west and east below/at/above the statutory five-foot side reference (1.374/1.524/1.674 m commanded body-edge gap), and three source-distinct necessity exceptions for lawful traffic conflict, police direction, and traffic-device direction. Ten comparisons isolate activity, side gap, side, or exception source. Five feet is a geometric reference; no legal measurement convention or verdict is inferred. The separate chute object is outside this frozen sidewalk-elevator branch. The accepted evidence inventory is empty.
- `parking.py` validates municipal/sidewalk/fixture/curb/one-way/map/vehicle/camera sources, constructs or locates a physically present fixture and verifies identity/geometry readback before the ego, commands a curb body interval, and cleans up owned resources on failure. It measures original contiguous vehicle-body intervals, curb gaps, activity observations and sourced exception circumstances without substituting setpoints for observations. `audit_comparison` rejects absent deliberate differences and changed fixed conditions.
- `saved_audit.py` checks a SHA-256-sealed 900-frame original Native JSONL at 20 Hz, fixed fixture/map/jurisdiction/sidewalk/camera joins, physical-presence readback, body footprint and exception source. Fixture readback in a CPU fake only checks call flow; actual physical visibility remains unverified.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver/tests -v` passed 6 tests; see `cpu-tests.log` and `result.json` SHA-256. Tests exercise both side boundaries, fixture creation/readback, cleanup, missing exception source, contiguous original measurements, comparison rejection, valid sealed 900-frame history and hash/source/frame tampering.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver --complete` passed static checks (`complete-check.log`). The same exact command with `--require-delivery-ready` exits 1 (`strict-check.log`) at partial-package acceptance. This is truthful: the per-case execution bundles, exact offline and positive/negative compatibility receipts, source-hashed diagnostic recipes, semantic proposals, and independent full-video delivery audit remain CPU construction/proof work.
- Resume by turning each planned case into a manifest bundle with a case-specific finalizer and source-hashed diagnostic; run `runtime.py offline` and `runtime.py compatibility` positive/negative for every case and risk-justified fallback; implement/process-saved and delivery/pixel audit fixture proofs; author stage proposals; rerun the exact strict assignment gate. Do not interpret a CPU fixture as a realized sidewalk elevator or legal exception.
