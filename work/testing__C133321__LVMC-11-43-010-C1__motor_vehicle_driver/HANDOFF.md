# testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.43.010(C)(1) — The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the left lane to turn left or complete a U-turn.
Assigned branch(es): Intended U-turn exit..
Cell: C133321 (multilane_roundabout, u_turn, lane_allocation); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and source-audit checkpoint

The exact frozen U-turn branch now has two cases, `__left_lane_u_turn` and `__outer_lane_u_turn`, in `case-plan.json`, linked by `u_turn_left_vs_outer_lane`. The comparison holds source-hashed map, jurisdiction, entry and opposite-direction exit, vehicle blueprint, controller, weather, cameras and duration fixed while changing the map-derived circular lane. No accepted recordings are listed in frozen evidence. The statute has no numeric boundary or judgment range for this assignment. Left-turn text is a distinct statutory alternative; the frozen C133321 cell is explicitly U-turn and this package does not claim a left-turn recording.

`roundabout.py` verifies a Native map readback, physical left-of-travel ordering, distinct allocated lanes, circular route arc and continuity, opposite-direction mapped exit, sealed full 900-frame original history, actor binding, observed ring lane and actual departure heading. `compare` rejects changed fixed conditions and missing original frames. Its CLI accepts exact map/history paths with SHA-256s and writes measured JSON; it does not infer a legal result. `runner.py` is a lazy adapter-driven 900-tick route tracker that spawns a motor vehicle, commands route tracking, seals source frames and destroys its actor in `finally`. The adapter must provide real CARLA map readback, world restoration, synchronized camera capture and Native sealing before live use; CPU fixture tests only verify call sequence and negative guards.

Test: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver/tests -v` (10 tests, exit 0, `cpu-tests.log`). Exact static command: `.venv-cpu/bin/python worker_check.py --assignment testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver --complete` (exit 0). Strict delivery gate remains partial.

Next CPU work: bind a source-surveyed roundabout/map and implement its concrete CARLA adapter with four-view capture and world cleanup; materialize exact per-case config/construction/manifest, source-hashed diagnostic recipes, offline and positive/negative compatibility receipts, canonical semantic proposals, saved-only processing and independent delivery/comparison audit receipts. Then rerun each exact gate and keep partial until strict passes. Physical lane tracking, visibility, duration and original recording review remain separate later checks.
