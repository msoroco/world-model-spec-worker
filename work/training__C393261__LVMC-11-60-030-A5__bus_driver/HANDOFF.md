# C393261 bus terminus delivery handoff

Status: **delivery prepared**. Two selected exact-cell Native cases pass the assignment-scoped strict CPU gate. No original CARLA run, accepted recording, physical acceptance, or legal violation is claimed.

## Source and legal boundary

The frozen assignment is `inputs/training__C393261__LVMC-11-60-030-A5__bus_driver/assignment.json`, SHA-256 `982834ae3f3ad99c221f2e54780fd0bb1e134a5534e00e5db40bc233dd86d77a`. LVMC 11.60.030(A)(5) applies to a non-tour bus standing or parking at a bus stop or origin/destination point longer than the period designated for that location under LVMC 11.60.010. Neither the law nor frozen cell supplies a numeric period or its establishing authority. A sign need not display that period. The Native capture and finalizer therefore keep endpoint authority, period, and legal comparison unverified until original source review supplies them. Synthetic 8 s and 18 s dwell measurements are engineering diagnostics, not legal cutoffs.

## Selected cases and execution

`probe_01` requests an 8 s complete stationary dwell; `probe_02` requests 18 s. Both use the same residential route terminus road, non-tour bus policy, 30 s at 20 Hz, and canonical synchronized overview, approach, reference-corner and driver-reference cameras. Each selected `cases/probe_0i/construction.json` packages `native/runner.py`, `native/geometry.py`, `native/measure.py`, `native/finalize.py`, config, source review, and tests. The runner surveys the parking lane and marker, records original bus pose and velocity, camera frame map, Core trace/capture, and a hashed terminus review, then restores the world and releases ownership. The finalizer joins bus activity to original frame and camera sources and leaves authority-dependent judgment unknown without an official, hashed designation and period source.

The exact first GPU delivery command is in `result.json`. Use the source-gated survey on the intended map, verify non-tour bus blueprint and actual standing/parking activity, attach the official endpoint designation and applicable period under Section 11.60.010, and run both selected cases. Retain original videos, trace, capture manifest, terminus history/context/review, and the source hashes. Apply `delivery_audit.py` to each original attempt before any physical or legal acceptance.

## CPU proof ledger

- Both current-runtime offline preflights passed without simulation, and both public compatibility runs passed original-source positive and missing `terminus-context.json` negative checks. Receipts and logs are under `native/proofs/probe_01/` and `native/proofs/probe_02/` and bound in `execution-manifest.json`.
- Both materialized recorded-only diagnostic attempts passed `process-saved`; their processing receipts are bound under each case's `post_capture`. These tests do not replay Native motion.
- `physical_proof.py` checked complete, incomplete, and missing diagnostic motion plus capture, encoder, restoration, ownership, and saved-processing lifecycle order. `delivery_audit.py` positive selftests and synthetic-source rejection are bound per case.
- `comparison_audit.py` independently verifies source hashes, fixed road, camera, duration and actor, two distinct measured dwells, and an unknown legal comparison. Its receipt is `native/proofs/comparison.json`.
- Semantic delivery validation passed six stages for both cases; the three Native unit tests pass. Exact scoped strict: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c393261-proof TMPDIR=$PWD/.runtime-work/c393261-proof .venv-cpu/bin/python -B worker_check.py --assignment training__C393261__LVMC-11-60-030-A5__bus_driver --complete --require-delivery-ready` exited 0.

Remaining local review: original physical bus placement and motion, four-view visibility, official endpoint and designated period authority, actual bus activity classification, and independent physical/legal acceptance. Diagnostic fixture success does not establish accepted membership.
