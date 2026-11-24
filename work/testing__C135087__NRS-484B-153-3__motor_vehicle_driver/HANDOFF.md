# testing__C135087__NRS-484B-153-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.153(3) — A person shall not leave open a door on the side of a vehicle which is closest to passing traffic longer than is necessary for immediate loading or unloading of passengers or cargo.
Assigned branch(es): Door-open duration during narrow-road loading.
Cell: C135087 (narrow_road, load_unload, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C135087__NRS-484B-153-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 door-side and loading measurement checkpoint

The exact law has no numeric duration cutoff. `case-plan.json` now has five unlabeled exact cases for cargo/passenger loading, active versus inactive open periods, and a door on the opposite side from passing traffic. Four comparisons reuse the same cases and list their fixed conditions and deliberate differences. The frozen accepted evidence inventory is empty; the gap is explicit. `measurement-contract.json` maps the original frame map, door articulation, loading activity, separate passing body/path and narrow-road geometry to measured outputs. Legal necessity and immediacy remain unresolved.

`door_measurement.py` independently reopens and SHA-checks all five original packets, verifies 20 Hz frame/time joins, selected-vehicle door/activity identity, actual separate passing longitudinal traversal during the door-open interval, lateral road/body clearance, opening and closure, and active/inactive loading durations. `comparison_audit.py` remeasures both original attempts and checks path/geometry/time isolation plus each declared difference. These are CPU saved-source components; no live Native capture is asserted. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C135087__NRS-484B-153-3__motor_vehicle_driver/tests -v` passed 10 focused tests, including all four comparisons and tamper/absence failures. Log SHA-256 `d40bbcc71ef175614ca826483134157060be869db846adb956444d35174bf5bd`. Scoped `--complete` static check passed; exact strict gate exited 1 because result is correctly partial (`cpu-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: construct source-verified narrow-road/vehicle/door/loading assets and controllers, acquire original source packets and four cameras under pinned Native lifecycle, then author all exact construction bundles, canonical proposals, offline and positive/negative compatibility, process-saved and independent delivery audits. Actual door/passing motion and pixels remain later local physical review.
