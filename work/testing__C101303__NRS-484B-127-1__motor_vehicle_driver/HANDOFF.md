# HANDOFF — testing__C101303__NRS-484B-127-1__motor_vehicle_driver (PARTIAL)

Law: NRS 484B.127(1), exact text in `inputs/<id>/assignment.json`. Cell C101303 (hill crest, change_lane, other_vehicle control).
Witness branch "Following before a lane change". Reasonable-and-prudent distance is **not** measured or judged; no gap/speed/duration is a legal threshold.

## Status: partial, CPU-prepared core only. No `result.json` is written on purpose
Any `result.json` beside a `construction.json` makes `worker_check.py` demand the whole ready gate (manifest, physical-preparation
receipts, compatibility receipts, delivery audit, semantic stage chain, fallbacks, queue, integration proof). Those are NOT done, so a
`partial` result would fail static checks. Nothing here claims physical, legal or canonical acceptance.

## What exists and works (Python 3.11, CPU only)
- `scenario.py` — pure Python: generated OpenDRIVE (two same-direction lanes -1/-2, parabolic crest at s=450 m, 120 m vertical curve, 3% grades),
  8-case parameter table (base + 7 single-variable variants), speed PI, gap-hold, smoothstep lane change triggered by road position, kinematic `preview()`.
- `runner.py` — Native CARLA runner (CARLA imported lazily). `--check` is CPU-only. Spawns ego/lead(/queued) on the generated map, four synchronized RGB cameras
  (1920x1080 + 3x1280x720, lossless ffv1 .mkv, 20 Hz), `PipelineCapture` per tick, `FrameMap`, `following_samples.jsonl`, channel streams, `surface_context.json`,
  world restore + `seal_capture`. **Never executed against CARLA.**
- `analyze.py` — saved-only finalizer: eight case-specific measurements, target checks, `physical_result`/`write_result`. Missing `surface_context.json` raises
  `Missing required source: surface_context.json`.
- `tools/build_constructions.py` — regenerates `construction.json` (base, root) and `cases/<variant>/construction.json`; shared files are referenced by `source`.
- `case-plan.json` — 8 cases, 7 comparisons (`base_vs_<variant>`; base is an explicit shared reference), 8 selected requirement dispositions, camera plan.
- `execution-manifest.json` — **minimal** (case id, construction, hash only; `status: partial_offline_only`). Not gate-valid.

## Checks run
- `python -m unittest discover -s work/<id>/tests` -> 14 tests OK (`cpu-tests.log`).
- `python runtime.py offline --manifest ... --case <each of 8>` -> exit 0 for all 8 (`runtime-offline-receipts.json`, `logs/`). This runs `runner.py --check` and the bundled tests; no simulation.
- Core atom preflight on `config.json` required_atoms -> passed (`ru.subject kin.speed kin.position rel.ahead_behind_in_lane rel.surface_gap st.lane st.crest st.grade`). Passing means a possible adapter path, not that values exist.
- Lean decoder built locally (`runtime.py build-decoder --library runtime/library --lake <elan lake>`) into ignored `.runtime-work/decoder`; not used further.

## Not done / exact failures
1. `runtime.py selftest` -> `ValueError: Optional runtime smoke fixture was not exported` (`runtime/fixtures/retained-speed` absent in this clone).
   The compatibility / process-saved path (`convert` -> decoder -> render) needs a complete Native capture tree (`capture/evidence.jsonl` with `original_observations`,
   `capture/native/frames.jsonl`, `capture/manifest.json` with source hashes, recorder log, `road.xodr`). No frozen example of that format is in the clone;
   hand-synthesising one would be unverified, so the exact-case positive/negative compatibility receipts were not produced.
2. `runtime.py preflight-native --python <py>` -> `ModuleNotFoundError: No module named 'carla'` (expected; no CARLA here).
3. Missing for the ready gate: `execution-manifest.json` full fields (measurement_contract, fixture_recipe, measurement_procedure, acquisition, physical_preparation,
   compatibility, negative, candidate_risk, delivery_acceptance), `proposals/cases.json` + `proposals/semantic-index.json` stage chain, `work/_shared/gpu-queue.json`,
   `local-integration-proof.json`, `branch-coverage.json`/`branch-review.json`, risk assessments/fallbacks (e.g. wet_surface friction, lead_brakes ego following), independent delivery audit script.
4. `FULL_BRANCH_CONTRACT.md` cites `inputs/coverage/branch-sources.json` and candidate-cells; `inputs/coverage` is absent (and batch.json does not set full_branch_coverage_required),
   so topic coverage was not enumerated. Only the single assigned branch is planned. Law alternatives are not decomposed further (the exact text has no exceptions).
5. Demo-train comparison preflight (FULL_BRANCH_CONTRACT) not performed: no accepted demo-train data in the clone. `review-context/README.md` quotes placeholder law text; exact text taken from `assignment.json`.

## Remaining GPU checks (unconfirmed)
Actual motion and lane-change completion, crest geometry in CARLA, lead braking/leaving behaviour, wet-surface effect, four-camera visibility of both vehicle bodies, 45 s / 900 frame duration, encoder/restoration behaviour.
Resume: `python3.11 work/<id>/tools/build_constructions.py`, then `python runtime.py capture --manifest work/<id>/execution-manifest.json --case <id>__base --output <new dir> --host $CARLA_HOST --port $CARLA_PORT --python "$CARLA_PYTHON"` (only after the gate fields above exist).
