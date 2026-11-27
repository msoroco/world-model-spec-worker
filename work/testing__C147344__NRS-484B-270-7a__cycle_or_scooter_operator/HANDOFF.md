# C147344 handoff — 2026-11-26

Status: partial CPU package for exact NRS 484B.270(7)(a), Class 1 electric-bicycle operator in C147344. No original recording, physical acceptance, subjective-intent finding or legal verdict is claimed.

## Exact scope and evidence

The law prohibits intentional interference with movement of a motor vehicle. The frozen witness selects the electric-bicycle operator branch and requires a qualifying Class 1 electric bicycle, a distinct statutory motor vehicle, actual movement and intent evidence kept separate from physical outcomes. Frozen `evidence.json` lists no accepted recording. The exact-law judgment-range inventory has no applicable range. `case-plan.json` records the source review and gap.

Four exact cases: `planned_merge_braking`, `planned_merge_no_braking`, `ordinary_merge_braking`, and `hold_lane_braking` under this assignment ID. Three controlled comparisons: `merge_effect` holds the authored plan and bicycle path fixed; `intent_source` holds physical requests fixed and varies only the source-bound authored declaration; `merge_presence` holds motor response and absent declaration fixed while varying the bicycle path. These are observation contrasts, not legal findings. No physical trace alone proves intentional interference.

## Implemented CPU construction

`interference.py` requires source-qualified wheels, pedals, saddle, <=750 W motor, pedaling-only assistance ceasing at 20 mph, moped/scooter exclusions, distinct motor vehicle, reviewed road, routes and lane assignment. It spawns both participants and requests controlled routes. `runner.py` hashes independently reviewed source files and checks their contents against scene fields, checks the live OpenDRIVE hash and route readback before actor creation, captures 600 original 20 Hz frames and four cameras, destroys owned actors and restores the original world. It seals original source hashes without rewriting acquisition. The local adapter implementation and Native model selection remain for integration review.

`analysis.py` verifies the sealed original source manifest, exact case, 600 frame identities, participant and camera sources, and produces a non-accepting Native result. `comparison_audit.py` rejects missing original source seals or changed fixed conditions. The case bundle includes tests for all these paths.

## Proof status

- Current pinned runtime verify and preflight passed. Four exact `runtime.py offline` materializations pass; their commands and logs are `proof-offline-*.log`, and scratch outputs are under `.runtime-work/c147344-owner/offline-v6-*`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator/tests -v` passes 18 tests; log `cpu-interference-tests.log`.
- `prove_physical.py` uses the pinned runtime physical checker under `PYTHONPATH="$PWD/runtime"` with `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c147344-owner/runtime-output"`. All four cases have `physical-complete_motion.json`, `physical-incomplete_motion.json`, and `physical-missing_evidence.json` plus logs. These are synthetic checker fixtures, never CARLA claims.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator --complete` passes as a partial checkpoint. Strict readiness presently fails because result remains truthfully partial.

## Exact next CPU work

1. Bind the selected requirement to measurement contracts and diagnostic recipes for all four cases. Run current-runtime positive and missing-source compatibility, including converter, Lean and full video decode.
2. Prove recorded-only saved processing and feedback. Add independent delivery audit with positive and negative source/pixel checks and comparison audit receipts.
3. Finish canonical stage proposals, exact final execution manifest, physical risk fallback with exact offline/compatibility proof, and four-row concrete queue proposal. Review statutory and comparison coverage independently.
4. Pass `.venv-cpu/bin/python worker_check.py --assignment testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator --complete --require-delivery-ready` before changing `result.json` to ready. Physical original source, motion and pixels remain later local checks.
