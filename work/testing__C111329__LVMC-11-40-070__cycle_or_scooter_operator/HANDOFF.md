# testing__C111329__LVMC-11-40-070__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.40.070 — Any person operating a bicycle, electric bicycle, or electric scooter shall obey the instructions of official traffic-control signals, signs and other control devices applicable to vehicles, unless otherwise directed by a Police Officer.
Assigned branch(es): Official device instruction with Police Officer exception retained.
Cell: C111329 (intersection, travel, traffic_control_device); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__LVMC-11-40-070__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 exact-case construction checkpoint

The original law independently requires a bicycle/electric bicycle/electric scooter operator to follow applicable official vehicle traffic-control signals, signs and other devices, except when a Police Officer directs otherwise. Frozen C111329 selects the cycle/scooter role and an intersection travel device. This checkpoint chooses a human-powered bicycle within that role; no alternative device class is asserted covered. Frozen evidence inventory has zero accepted recordings and the exact-law judgment-range inventory has zero matching ranges. No numerical legal threshold is inferred.

`case-plan.json` now binds nine exact case IDs: `signal_red_stop`, `signal_red_cross`, `signal_green_cross`, `signal_red_officer_proceed`, `signal_green_officer_stop`, `stop_sign_stop`, `stop_sign_cross`, `other_device_hold`, and `other_device_cross` (all prefixed by this assignment ID and `__`). Six comparisons isolate operator motion, signal instruction, or officer direction. Every case lists required original Native sources and a physical-risk assessment. A stop sign and no-entry device are included as sign and other-device examples; their actual legal/vehicle applicability remains a local source requirement.

`native_device.py` validates a SHA-pinned original site packet, map/device identity, official authority and vehicle applicability citations, spawns a source-identified bicycle with readback and cleanup, and checks full original 20 Hz device/body/officer history against a source stop line. `native_route.py` actuates the source route for crossing/holding and records velocity readback without legal labeling. `comparison_audit.py` rejects missing original source, identity, context, fixed-condition drift or absent declared differences. `tests/test_native_device.py` and `tests/test_native_route.py` exercise positive calls and negative branches: six tests pass. Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__LVMC-11-40-070__cycle_or_scooter_operator/tests -v`; log `cpu-tests.log`, SHA-256 recorded in `result.json`.

The exact strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__LVMC-11-40-070__cycle_or_scooter_operator --complete --require-delivery-ready` fails with `Preparation acceptance failed: partial/missing packages remain`. Status remains partial. Native site and officer authority are source gates, not demonstrated scene facts. Officer actor/gesture construction, timed direction, stop-compliance trajectory, canonical proposals, complete runner/manifest, exact diagnostic and compatibility proofs, saved-only receipt, independent delivery audit and queue remain CPU work. The Native code does not yet satisfy end-to-end delivery readiness. Resume by implementing those in this directory, then rerun the exact gate. Actual motion and pixels are later physical checks; they are not asserted here.
