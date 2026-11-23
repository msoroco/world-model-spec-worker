# testing__C111748__NRS-484B-403-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.403(2) — If an official traffic-control device indicates that a U-turn is prohibited, the driver shall obey the directions of the device.
Assigned branch(es): Applicable official-device duty, including observation before any attempted turn..
Cell: C111748 (intersection, u_turn, turn_prohibition_device); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111748__NRS-484B-403-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable CPU checkpoint

The frozen evidence inventory is empty. `case-plan.json` now defines three exact cases: `__prohibited_obey`, `__prohibited_attempt`, and `__neutral_device_turn`. The `device_obedience` comparison changes only the driver's U-turn action after observation. The `device_applicability` comparison changes only the reviewed device direction while retaining the driver turn. All cases require a physical-risk review for sign legibility and U-turn route envelope; fallback constructions remain to be implemented and proved if needed.

`construct.py` loads a SHA-sealed, case-bound site, requires original map/highway/official-device/display sources and an opposite-lane route, and lazily spawns the motor vehicle and device with failure cleanup. `native_device.py` measures a SHA-sealed original-frame packet, rejects gaps, identity or live-display mismatches, missing governed-approach frames and visibility, and detects whether a turn starts after device visibility. Its `visible_to_ego` readback requires later video review; it does not establish actual driver perception or legal device status. The original law has no numeric threshold. The conditional official-device applicability needs reviewed placement authority, regulatory purpose and external legal-consistency evidence.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111748__NRS-484B-403-2__motor_vehicle_driver/tests -v` passed 9 tests. The exact log/hash is in `result.json`.

Next CPU work: add source-bound full-turn pose/heading corroboration; implement exact per-case runner/config/construction bundles, measurement contracts, semantic proposals, execution manifest, source-hashed positive/negative compatibility fixtures, saved-only processing, independent delivery and comparison audits, and risk-triggered candidate fallback proofs. Review the full statutory device clause independently before a ready claim. A later CARLA run must verify route motion, actual sign pixels and four-camera coverage. No package here is ready yet.

The saved measurement now additionally rejects a claimed completed U-turn unless original ego poses show at least 135 degrees of heading reversal and an opposite destination lane on the same road. The focused suite passes 10 tests; `result.json` binds the renewed log hash.

`comparison_audit.py` independently reruns both sealed Native sources. It verifies the exact obedience/applicability case pairs, fixed map, route, actor, highway, official-device authority, governed approach, camera plan, duration and frame window; then verifies exactly the declared driver-action or display-direction difference. It produces no legal conclusion. Positive and negative CPU tests cover both pairs, fixed-route drift, missing action difference and source tampering. The focused suite now passes 15 tests; see renewed `cpu-tests.log` and `result.json` hash. This is a saved-source comparison component, not a completed delivery audit or exact manifest proof.
