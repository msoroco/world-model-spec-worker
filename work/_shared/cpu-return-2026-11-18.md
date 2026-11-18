# CPU preparation continuation — 2026-11-18

This report supersedes the earlier `cpu-checkpoint-2026-11-18.md` snapshot. The pinned Python CPU requirements, ffmpeg, ffprobe, Lean and lake are installed. `.venv-cpu/bin/python runtime.py preflight` exits 0. Missing package dependencies and missing tool diagnoses are closed.

## Verified assignment closures

`training__C10014__NRS-484B-477-2__motor_vehicle_driver` and `training__C10316__NRS-484B-293__pedestrian` are `ready` for CPU handoff. Each has two selected exact cases and eight regenerated primary/fallback offline, positive/negative compatibility and recorded-only saved-processing chains under the current JSON graph runtime. Their independent source audits, delivery audits, assignment tests and assignment-scoped `worker_check.py --complete --require-delivery-ready` gates pass. These are software diagnostic proofs; original Native motion, camera pixels, physical completion, canonical acceptance and legal judgment remain unconfirmed. See each assignment's `HANDOFF.md` and `result.json` for exact commands and hashes.

The old diagnostic `.pkl` graph paths were migrated to `.adapter.json` with `adapter_graph` frame pointers. Synthetic motion fixture results now declare `provenance_kind: synthetic_fixture` and `diagnostic_fixture: true`. Old proofs remain historical. The shared queue had 89 historical `ready` rows for currently partial assignments; `queue-readiness-reconciliation-2026-11-18.json` records their demotion. No dispatchable field was changed. The queue remains noncanonical and nondispatchable.

## Next assignment in progress

`training__C104538__NRS-484B-407__motor_vehicle_driver` remains `partial`. All three selected case diagnostic recipes and nine candidate-specific fallback recipes now use live adapter JSON graphs. Nine synthetic physical outcome fixtures and three lifecycle fixtures pass. The first exact selected primary and fallback1 compatibility and saved-processing paths pass. The full 12-chain proof matrix is running in `run-current-selected-update043f.py`; it must be bound, independently audited, followed by delivery audit, assignment tests and the scoped strict gate before readiness. Previous failed update043b/c/d logs document repaired worker-owned adapter path, candidate context and fixture fingerprint issues.

## Batch blockers and resume

Current batch result markers are 2 `ready`, 251 `partial`; the remaining 251 assignments need current-runtime exact proofs and assignment-scoped strict gates. The canonical ordered GPU queue, local integration proof and full independent branch review also remain batch work. The full strict gate cannot pass with partial assignments. The latest supplied full-gate trace rejects the generated `runtime/pipeline/runs/scenario_pipeline/state/cache/maps/a8904fe0fe1bc426462e8065a67fc12be18fe78961b794a9781d5731d0783113.lock`. That file still exists and is under frozen `runtime/`; it has not been edited or removed. Future CPU runs should set `SCENARIO_PIPELINE_OUTPUT_ROOT` to ignored `.runtime-work/` to prevent new runtime-cache output there.

No frozen input, runtime source, or `batch.json` was edited. No Git command was run; publication remains with the separate timer.
