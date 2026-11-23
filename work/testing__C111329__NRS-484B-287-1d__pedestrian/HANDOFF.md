# testing__C111329__NRS-484B-287-1d__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.287(1)(d) — Except as provided in NRS 484B.290 [LVMC-11-30-140-B]: A pedestrian shall not cross an intersection diagonally unless authorized by official traffic-control devices.
Assigned branch(es): Pedestrian travel across an intersection.
Cell: C111329 (intersection, travel, traffic_control_device); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1d__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and comparison checkpoint

The full NRS 484B.287(1)(d) text was reread independently. It distinguishes an adjacent-corner crossing, an opposite-corner diagonal crossing without official authorization, and a diagonal crossing authorized by an official pedestrian-governing device. The referenced NRS 484B.290 exception remains unresolved in the supplied source; no legal classification or exception claim is made. No accepted recordings exist in the frozen evidence inventory.

`case-plan.json` now contains four exact cases: `adjacent_no_diagonal_authority`, `diagonal_no_authority`, `diagonal_authorized`, and `adjacent_authorized_device`, each prefixed by this assignment ID, with three controlled comparisons: `diagonal_path_without_authority`, `diagonal_device_authority`, and `authorized_device_path_control`. All retain the same measured intersection, 20 Hz and camera/duration conditions in the intended comparisons. Each case has a concrete physical-risk assessment. No fallback is claimed until an exact source-bound site construction and CPU proof exist.

`native_crossing.py` builds 21 measured waypoint positions from a four-corner source packet, requires map and intersection provenance, rejects an unverified official/pedestrian-specific diagonal authorization, commands a spawned walker through a lazy adapter, reads identity, and destroys it on command failure. `saved_measurement.py` rejects gaps in original-frame walker/device histories, identity discontinuities, absent endpoints and absent official device sources; it measures observed intersection traversal without deciding legality. `comparison_audit.py` tests fixed map, body, camera and duration sources as well as deliberate route/authorization differences.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1d__pedestrian/tests -v` passed five tests in `cpu-tests.log`; SHA256 `2d94c9d12b690495d2fd5cb3b5d8411345493e7be6cc0148ce137d29ac1f17b5`. Exact strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1d__pedestrian --complete --require-delivery-ready` failed with `Preparation acceptance failed: partial/missing packages remain`; see `strict-check.log`.

Next CPU work: bind a real map/device source packet, add the exact runtime runner/config/construction and case-specific diagnostic recipes, execute offline and positive/negative compatibility proof per case, build semantic proposals, saved-only processing and independent delivery audit, and rerun the strict gate. The modules here are implementation probes and do not yet establish delivery readiness. Later GPU checks are physical route completion, device state, camera visibility and capture quality.
