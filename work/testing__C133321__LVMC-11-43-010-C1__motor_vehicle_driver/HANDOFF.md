# C133321 U-turn lane preparation

Assignment: `testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver`.
Status: ready for original-device execution; exact assignment CPU delivery gate passed on 2026-11-26.
Law: LVMC 11.43.010(C)(1), use of the left lane to complete a U-turn when exiting a roundabout. The frozen cell is a multilane roundabout, U-turn and lane allocation. The separate left-turn statutory alternative is outside this frozen cell. Frozen accepted recordings and judgment range entries for this law and actor: zero.

## Prepared cases and comparison

- `__left_lane_u_turn`: requested allocated left lane, opposite-direction exit.
- `__outer_lane_u_turn`: requested allocated outer lane, same exit and fixed conditions.
- `u_turn_left_vs_outer_lane`: fixed map, jurisdiction, entry, exit, actor blueprint, controller, weather, camera plan and duration; allocated lane changes.

`native_capture.py` requires a source-hashed reviewed survey, operator and loaded OpenDRIVE/map readback before changing the world. It captures 900 consecutive 20 Hz original Native frames, actor pose and body geometry, map lane and section identity, and four original camera streams. It restores world settings and destroys actors and sensors. `roundabout.py` verifies the source map's left-of-travel lane order, connected circular routes, opposite exit, observed lane and actor, mapped position corridor and completed U-turn arc. The source gate rejects a stationary actor whose metadata alone reports a ring traversal. `native_output_bridge.py` seals original packets into a trace, frame map, evidence and four FFV1 views for runtime processing.

The selected and fallback constructions, source-shaped diagnostic recipes, canonical semantic proposals and execution manifest are in this assignment folder. The diagnostic nine-frame fixture is explicitly marked as such; it is CPU proof material, not original CARLA evidence. No accepted recording or physical/legal result is invented.

## Current-hash CPU proofs

The source-hashed build was regenerated after the mapped-arc guard. Both cases passed primary and fallback offline plus positive and negative compatibility; both passed saved-only positive and missing-source checks, physical/lifecycle fixture checks and independent delivery positive and negative audits. The comparison passed independent positive and negative audit. Sixteen assignment unit tests passed. Evidence is recorded in `cpu-*.log`, case construction files, `execution-manifest.json` and selected semantic proposals.

Exact gate: `PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c133321-owner-nov26/pipeline" TMPDIR="$PWD/.runtime-work/c133321-owner-nov26/temp" .venv-cpu/bin/python worker_check.py --assignment testing__C133321__LVMC-11-43-010-C1__motor_vehicle_driver --complete --require-delivery-ready` exited 0 with `static_checks_passed: true`.

Manifest SHA-256: `8f42a817605d98f6128b41c08df007db61cdd462b429184cc4efe9ba815730c5`.
Queue proposal SHA-256: `e4449aaadfbdbcf25f0ec11e9911b846fb6e06acdfceba2ffc5626942f0d0f39`.

## Local review still required

An original reviewed roundabout survey and operator must establish the specific map, jurisdiction and applicable left-lane allocation. Local CARLA execution must verify physical motion, four-view visibility and original pixels. Independent reviewers must assess statutory applicability and legal meaning. `gpu-queue-proposal.json` supplies commands for that later acquisition and audit; it claims only CPU delivery preparation.
