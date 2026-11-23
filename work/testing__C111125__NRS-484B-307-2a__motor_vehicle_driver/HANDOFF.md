# testing__C111125__NRS-484B-307-2a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(2)(a) — When the signal is circular green alone: Vehicular traffic facing the signal may proceed straight through or turn right or left unless another device at the place prohibits either or both such turns. Such vehicular traffic, including vehicles turning right or left, must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.
Assigned branch(es): Straight movement under circular green alone.
Cell: C111125 (intersection, straight, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Controlled case and Native-source checkpoint, 2026-11-23

The source inventory has zero accepted recordings, so no existing-evidence reuse is claimed. `case-plan.json` now proposes four exact cases: `green_clear`, `green_vehicle_present`, `green_pedestrian_present`, and `green_pedestrian_late`. All use the fixed C111125 straight intersection and sole circular-green signal. Three comparisons vary intersection vehicle presence, adjacent-crosswalk pedestrian presence, and pedestrian region at first green exhibition. The late case preserves the statutory “at the time the signal is exhibited” distinction. No numerical right-of-way threshold or lawful-presence conclusion is invented. Each case has a physical risk assessment. The provided judgment range file has zero entries for this exact law and actor.

`native_scene.py` verifies hashed original map, official signal, straight route, and adjacent-crosswalk sources; checks that the route actually crosses the surveyed intersection; checks real Native map and official signal-head readback; then spawns ego and optional other user through the injected CARLA interface. It destroys spawned actors after a later spawn failure. `measure_attempt` reads hashed original frame events, preserves first green exhibition and each user's original region then, and records later motion separately. It returns no legal verdict. `straight_control.py` supplies conservative approach/hold/proceed engineering control gated by the observed signal and measured user region. `comparison_audit.py` independently rejects wrong exact case pairs, changed fixed-source hashes, missing exhibition data, and missing or incorrect region differences. These modules have not been wired into complete execution bundles or the saved pipeline.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-2a__motor_vehicle_driver/tests -v`. Six tests pass, including source-hash rejection, actual spawn calls, straight-route geometry, original exhibition timing, controller behavior, and negative comparison audit branches. The result records the hashed log. The exact strict assignment command ran and failed with `Preparation acceptance failed: partial/missing packages remain`, as expected for the truthful partial status. See `cpu-strict-check.log`.

Next CPU work is to connect these case controllers and measurements to each exact construction/config/runner bundle; add a source-hashed diagnostic recipe and selected-requirement finalizer for every case; run each offline and positive/negative compatibility proof; author semantic proposals, execution manifest, saved-only processing tests, and independent delivery audit. A real Native map/head survey and physical replay remain necessary later to prove phase, positions, lawful-presence context and camera visibility. This is not an external blocker for the remaining CPU preparation.
