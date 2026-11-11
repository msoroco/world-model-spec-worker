# Handoff: heldout__C109705__NRS-484B-400-4__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a one-way highway onto a two-directional highway, the left turn must be made by passing to the right of the centerline of the highway being entered upon leaving the intersection, and the approach for the left turn must be made as close as practicable to the left-hand curb of the one-way highway.

Cell C109705: intersection / left_turn / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- One-way source highway to two-directional destination, left turn at intersection: compare measured approach body position relative to left curb with held departure.
- Compare destination body position right of entered centerline on leaving intersection with held approach.
- “As close as practicable” has no numeric legal cutoff; retain geometry, body footprints, feasible obstructions and alternative position measurements.

## Current checkpoint

Three cases compare measured approach body distance from the one-way road left curb with departure held fixed, and measured departure body side of the two-way road centerline with approach held fixed. Original four-corner footprints and map lines are required; no practicability cutoff is invented. Tests reject wrong road geometry, absent phases and changed held positions.

Implemented and CPU-tested: turn_geometry.py, turn_comparison_audit.py. The `cpu-tests.log` SHA256 is `3afb3f68b624e9e2d90264cb0c3b196d0a2e3a5c18ae947e08b9bd7a151409df`. These measurements are descriptive engineering observations and do not establish physical visibility or legal compliance. Status remains partial.

## Exact next CPU work

1. Review the new case plan against exact law and source topics; complete any missing alternatives or exceptions while preserving fixed cell/actor scope.
2. Exact Native constructions, four-camera capture, finalizer integration, three fallback constructions per case, offline/compatibility and saved-processing receipts, semantic proposals and delivery audit remain CPU work.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, then `runtime.py process-saved` on retained synthetic sources. Integrate the CPU-tested measurement and comparison audit with exact source bindings, and test independent delivery rejection paths.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C109705__NRS-484B-400-4__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete`. The strict readiness gate still fails because this package is partial; do not mark ready until every exact case and fallback passes its source-bound proofs.

## 2026-11-11 construction and first exact delivery checkpoint

The selected branch is a **one-way approach to a two-directional entered highway**. Corrected stale branch-analysis text that had reversed those directions. `turn_native_runner.py` now chooses a connected left turn through a Native junction with original OpenDRIVE lane directions, commands approach/departure lateral offsets, and retains four synchronized camera streams, map curb/centerline lines and every subject ground-body corner. `turn_finalizer.py` measures the original corner distances from the curb and signed positions relative to the entered centerline. It verifies JSON/JSONL footprint identity and trace/frame-map/time joins before writing two timestamped channels. It asserts neither actual physical completion nor legal practicability.

The first exact case, `approach_near_depart_right`, passes all ten CPU unit tests, fresh offline construction, positive and missing-`road_geometry.json` negative compatibility, and saved-only processing on a marked synthetic diagnostic. Original acquired files were unchanged after saved processing. Proof logs and SHA256 values are recorded in `result.json`; the saved receipt is `saved-first.json`. The diagnostic transfers Core graph and source video material from a prior synthetic fixture and adds C109705-specific map/footprint records; it is **not** an actual Native turn capture.

Status remains **partial**. Next worker CPU steps: construct and prove the `approach_far_depart_right` and `approach_near_depart_left` contrasts; add a finite original-position sweep for “as close as practicable” without a legal cutoff; bind three distinct physical-risk fallback constructions per exact case; run offline, positive/negative compatibility and saved processing; then run independent source comparisons, physical fixture outcomes, delivery audit and scoped strict readiness gate. Actual Native motion, camera visibility and legal practicability remain later checks after CPU preparation.

## 2026-11-11 three-primary contrast checkpoint

`expand_contrasts.py` binds current construction source for all three exact cases. Each primary has a distinct selected config, marked synthetic geometry/footprint diagnostic, measurement contract and source recipe. All three pass fresh offline and positive/negative compatibility proofs, then saved-only processing; saved receipts attest original acquisition bytes unchanged and make no physical or legal acceptance claim. `prove_contrast_comparisons.py` independently checks the near/far approach contrast with destination side held, and the right/left departure contrast with approach held. Its negative mutation changes the held departure and is rejected. The corresponding hashed proof logs are listed in `result.json`.

The assignment remains **partial** because a finite practicability sweep, three physical-risk fallbacks per exact case, source-shaped physical outcome fixtures and independent delivery audits have not yet passed. The diagnostic body footprints are authored CPU inputs, not evidence that CARLA drove the selected turn.
