# C149237 CPU handoff — NRS 484B.127(2)

Status: **partial**. The selected branch is qualifying truck following on the one-way-road/follow/truck cell. The exact statute requires both vehicles to be trucks or combinations at least 80 inches wide and, when conditions permit, 500 feet of space; it excludes highways with two or more lanes available in the same direction and preserves overtaking/passing. Frozen `evidence.json` contains zero accepted recordings, so no reuse is claimed.

`case-plan.json` identifies below/at/above 500-foot gaps, at/below 80-inch widths for each role, two same-direction lanes and overtaking. The statutory conversions are exactly 2.032 m and 152.4 m. These are measurements and target cases, not legal verdicts. Conditions permitting and whether an overtaker can occupy the space without danger require source review.

`truck_measurements.py` reads retained Native road context, both actors' overall widths and body vertices, same-lane road/lane IDs, and original frame-to-video mapping. It projects body vertices onto the sourced lane tangent to report longitudinal surface gap, rejects a wrong-lane lead or stale frame join, and reports same-direction lane count. Its output leaves conditions permitting, safe overtaker occupancy and compliance unresolved. `truck_construction.py` calls `try_spawn_actor` for two selected vehicle blueprints, checks actual bounding-box width, same Native lane, forward orientation and projected body ordering, then destroys both owned actors. Five CPU tests passed in `cpu-tests.log` using `.venv-cpu/bin/python -m unittest discover -s work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/tests -v`.

Earlier checkpoint: the Native map, truck blueprints, controller, source-camera runner and saved finalizer were still pending at this point. The later checkpoint below records their current implementation and outstanding proofs.

The pinned CPU runtime preflight passes; earlier package/tool diagnoses are resolved. No frozen input, runtime or batch file was edited.

Checkpoint: `.venv-cpu/bin/python worker_check.py --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --complete` passed; see `assignment-check.log`. The then-current batch strict gate failed at a missing result; the current gate fails because packages remain partial. See `batch-strict-current.log`. This is unfinished worker preparation, not an external blocker.

## Authored site and exact gap placement checkpoint (2026-11-11)

`native-map-plan/one-way-truck-road.xodr` is a 1200 m straight OpenDRIVE road with exactly one forward driving lane (road 149237, lane -1, 3.8 m wide). `truck_site.py` parses and checks that geometry and checks the selected `vehicle.carlamotors.european_hgv` and `vehicle.carlamotors.carlacola` identifiers against the pinned truck class map at `runtime/python/carla_sgg/actors.py`. `site-proof.json` binds both source hashes. The three planned gap targets are 150.0, 152.4 and 155.0 m; these are engineering case targets around the statutory 500 feet and do not decide whether conditions permit or an overtaker can safely occupy the space. The 5 m sample half lengths in `site-proof.json` are explicitly hypothetical.

`truck_construction.py:spawn_exact_gap_pair` now stages two actors, reads their realized bounding-box half lengths, moves the lead to the selected body-gap target, ticks the world, checks the authored road/lane and the realized gap, and destroys both owned actors on success or failure. It rejects widths below 2.032 m. The helper covers `__gap_below_500ft`, `__gap_at_500ft`, and `__gap_above_500ft`; it is now called by the first exact capture runner; CARLA execution remains unverified. Its class check is source-bound, while actual legal truck classification and combination overall width remain unresolved.

Commands and evidence:

- `.venv-cpu/bin/python runtime.py preflight` passed; `preflight-current.log`.
- `.venv-cpu/bin/python work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/truck_site.py work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/site-proof.json` passed; `site-proof.log` and `site-proof.json`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/tests -v` passed 17 tests; `cpu-tests-current.log`. The tests exercise actual XML lane topology, three surface-gap calculations, fake Native actor relocation, cleanup, narrow-width rejection, changed topology rejection, invalid or overlarge body lengths, an unclassified blueprint, and the two-truck following controller under explicitly assumed symmetric dynamics.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --complete` passed; `assignment-check-current.log`.
- Assignment and batch `--complete --require-delivery-ready` both fail with `Preparation acceptance failed: partial/missing packages remain`; `assignment-strict-current.log` and `batch-strict-current.log`. The result remains `partial`.

The `truck_follow_controller.py` policy applies the same longitudinal speed target and lane-centering command to both trucks at 20 Hz. A 900-frame symmetric toy-dynamics test keeps its modeled gap and lane position; this is controller software evidence, not a CARLA motion or 500-foot history receipt.

Next worker-owned CPU steps: complete the first case’s source-bound positive/negative compatibility and recorded-only saved-processing proofs with actual four-camera diagnostic media and Core conversion; then sweep the other two qualifying gap cases and the width, two-lane, overtaking and conditions-permit cases. Add three distinct risk-triggered fallback constructions per selected case, independent delivery and comparison audits, semantic proposals, and shared branch/queue/integration artifacts. Verify the nonqualifying-width cases use distinct constructions rather than this qualifying-pair helper. Actual CARLA motion, blueprint dimensions, map load, camera visibility and legal judgment remain future physical/source review, not explanations for the unfinished CPU implementation.

## First exact bundle and saved finalizer checkpoint (2026-11-11)

`runner.py`, `camera_setup.py`, `camera_encoder.py`, and `truck_capture_sources.py` now implement a prospective Native capture path for `testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__gap_below_500ft`. It loads the authored 1200 m OpenDRIVE road, uses pinned truck-class blueprint IDs, realizes the initial 150 m surface gap from spawned body lengths, applies the two-truck controller, joins 900 original Native ticks to four named lossless FFV1 source streams, retains complete body/width/road histories, and restores the operator-owned world. The software path has passed only CPU `--check` and fake actor/source tests; no CARLA capture or pixel claim has been made. `truck_site.py` also checks the constant-target-speed 45 s travel budget against the longer road with a conservative edge margin.

`build_primary_bundle.py` writes the source-bound `config.json`, `construction.json`, and a one-entry partial `execution-manifest.json`. It includes `finalizer.py`, which derives four measured channels from retained `truck_history.jsonl`, `road_context.json`, and `video_frames.jsonl` during saved analysis. `prove_finalizer.py` tested a three-frame source-shaped positive path, exact 150 m gap, and missing-history negative rejection. Its placeholder camera files are deliberately not decoded; this is not a compatibility or saved-processing receipt. The first exact bundle passed `runtime.py offline` with `--case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__gap_below_500ft`; see `primary-offline-current.log` and `primary-offline-tests.log`.

Current commands and evidence:

- `.venv-cpu/bin/python runtime.py preflight` passed: `preflight-current.log`.
- `PYTHONPATH=runtime/scenario_pipeline:runtime/python .venv-cpu/bin/python runtime/scenario_pipeline/worker_exchange/atom_preflight.py --runtime runtime --config work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/config.json` passed: `atom-preflight-current.log`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/tests -v` passed 17 tests: `cpu-tests-current.log`.
- `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__gap_below_500ft --output .runtime-work/c149237-gap-below-primary-offline-v2` passed: `primary-offline-tests.log`.
- `.venv-cpu/bin/python work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/prove_finalizer.py` passed positive and missing-source negative source-shaped tests: `finalizer-proof-current.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --complete` passed: `assignment-check-current.log`.

Exact next action: author a source-hashed 900-frame diagnostic recipe with all four real generated camera streams, source-shaped `capture/` and `trace.jsonl`; add a measurement contract and canonical semantic proposal; run `runtime.py compatibility` on this exact case, repair any converter/finalizer issue, then run `runtime.py process-saved` from the retained attempt. Keep the package partial until these and all remaining case/fallback/comparison/delivery proofs pass. The incomplete manifest has one of eight planned cases and no fallback receipts, so the strict gate is expected to reject it.
