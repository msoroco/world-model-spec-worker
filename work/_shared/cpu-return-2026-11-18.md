# CPU preparation continuation — 2026-11-18

This report supersedes the earlier `cpu-checkpoint-2026-11-18.md` snapshot. The pinned Python CPU requirements, ffmpeg, ffprobe, Lean and lake are installed. `.venv-cpu/bin/python runtime.py preflight` exits 0. Missing package dependencies and missing tool diagnoses are closed.

## Verified assignment closures

`training__C10014__NRS-484B-477-2__motor_vehicle_driver` and `training__C10316__NRS-484B-293__pedestrian` are `ready` for CPU handoff. Each has two selected exact cases and eight regenerated primary/fallback offline, positive/negative compatibility and recorded-only saved-processing chains under the current JSON graph runtime. `training__C104538__NRS-484B-407__motor_vehicle_driver` is also `ready` with three exact cases and twelve regenerated chains, including nine candidate-specific source recipes. All three independent source audits, delivery audits, assignment tests and assignment-scoped `worker_check.py --complete --require-delivery-ready` gates pass. These are software diagnostic proofs; original Native motion, camera pixels, physical completion, canonical acceptance and legal judgment remain unconfirmed. See each assignment's `HANDOFF.md` and `result.json` for exact commands and hashes.

The old diagnostic `.pkl` graph paths were migrated to `.adapter.json` with `adapter_graph` frame pointers. Synthetic motion fixture results now declare `provenance_kind: synthetic_fixture` and `diagnostic_fixture: true`. Old proofs remain historical. The shared queue had 89 historical `ready` rows for currently partial assignments; `queue-readiness-reconciliation-2026-11-18.json` records their demotion. No dispatchable field was changed. The queue remains noncanonical and nondispatchable.

## Next assignment

`training__C110454__NRS-484B-213-2b__motor_vehicle_driver` is the next assignment in batch order. It remains `partial` with nine selected cases and 36 candidate chains. Its retained diagnostic graph recipes still use `.pkl`; migrate them to the current JSON graph/capture contract, regenerate exact proofs, and run its scoped strict gate. Previous failed C104538 update043b/c/d logs remain as diagnoses of repaired worker-owned adapter path, candidate context and fixture fingerprint issues.

## Batch blockers and resume

Current batch result markers are 3 `ready`, 250 `partial`; the remaining 250 assignments need current-runtime exact proofs and assignment-scoped strict gates. The canonical ordered GPU queue, local integration proof and full independent branch review also remain batch work. The full strict gate cannot pass with partial assignments. The latest supplied full-gate trace rejects the generated `runtime/pipeline/runs/scenario_pipeline/state/cache/maps/a8904fe0fe1bc426462e8065a67fc12be18fe78961b794a9781d5731d0783113.lock`. That file still exists and is under frozen `runtime/`; it has not been edited or removed. Future CPU runs should set `SCENARIO_PIPELINE_OUTPUT_ROOT` to ignored `.runtime-work/` to prevent new runtime-cache output there.

No frozen input, runtime source, or `batch.json` was edited. No Git command was run; publication remains with the separate timer.
