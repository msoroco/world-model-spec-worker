# C109749 / NRS 484B.253: partial CPU checkpoint

Status is **partial**. The selected `testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn` case and its three physical-risk fallbacks pass the exact CPU software paths. The 43-package strict delivery gate still fails because partial packages remain. No physical or legal acceptance is claimed.

## Source and coverage

`case-plan.json` reviews the six accepted-recording metadata records and review-context groupings. The retained original trace/video bytes and per-frame delivery audits are absent from this export. Metadata establishes recording identity and decoder summaries, but cannot establish source-backed equivalence for `inside_yield`, `inside_no_yield`, `approaching_yield`, `approaching_no_yield`, `signal_omitted`, or `reciprocal_no_yield`. No accepted original is queued for replay. The selected new case covers initial opposing presence and subject yield, a signalled left turn after clearance, and a distinct later opposing actor slowing outside the junction. Its three selected requirement dispositions are in `case-plan.json`. “Immediate hazard” and right of way are legal judgments; no numeric legal cutoff is asserted. Other exact cases and controlled comparisons are unfinished CPU work.

## Construction and measurements

`runner.py`, `construction.py`, `controller.py`, `native_scene.py`, `capture_sources.py`, `camera_setup.py`, and `camera_encoder.py` construct a CARLA-lazy three-vehicle left-turn candidate. The runner records four named source-camera streams, original actor bodies/velocities/heading/indicator, FrameMap and Native trace at 20 Hz for 45 seconds. It closes encoders and restores the world before sealing. `measurements.py` measures initial opposing occupancy and clearance, subject turn and indicator sequence, and distinct later opposing movement/stop from original sources and a Native-derived junction envelope. `finalizer.py` regenerates required channels from retained `interaction_history.jsonl`, `intersection_geometry.json` and `video_frames.jsonl`; it hashes its sources, rejects missing original history, and makes no legal verdict. Native map geometry and actual body/pixel visibility remain unverified.

`execution-manifest.json` binds primary construction, measurement contract, diagnostic recipe, exact offline proof, positive/negative compatibility receipt, and recorded-only saved-processing test. Three fallback constructions under `cases/` vary controls actually consumed by the runner:

| Candidate | Changed control | Physical-risk trigger |
| --- | --- | --- |
| fallback1 | `controller_release_ttc_s`: 4.0 to 5.5 | initial opposing body remains in the junction at subject turn onset |
| fallback2 | `approach_speed_mps`: 5.0 to 6.0 | subject remains in the junction when the later opposing actor reaches its approach |
| fallback3 | `reciprocal_approach_speed_mps`: 2.5 to 1.5 | later opposing actor reaches the junction before subject body clearance |

Each fallback has its own embedded config, construction hash, exact offline log, positive/negative compatibility receipt, and recorded-only process-saved log bound in the manifest. Candidate selection must follow the observed trigger, never a desired legal outcome. These CPU proofs verify code paths, not that the tuning achieves physical motion in CARLA.

## CPU proofs and limits

- `.venv-cpu/bin/python runtime.py preflight` and the pinned atom preflight pass (`preflight.log`, `atom-preflight.log`). The 27 bundle tests pass in `cpu-tests.log`.
- Primary exact offline: `runtime.py offline --manifest work/testing__C109749__NRS-484B-253__motor_vehicle_driver/execution-manifest.json --case testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn --output .runtime-work/c109749-primary-offline-v4` (`primary-offline.log`).
- Primary exact compatibility: `runtime.py compatibility --manifest work/testing__C109749__NRS-484B-253__motor_vehicle_driver/execution-manifest.json --case testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn --output .runtime-work/c109749-primary-compat-v9 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck` (`primary-compatibility.log`, `primary-compatibility.json`). It passed finalizer regeneration, Native validation, Lean decode, renderer, full four-view video decode, three selected measurements, and negative deletion of `interaction_history.jsonl`.
- Primary recorded-only saved processing: `runtime.py process-saved --manifest work/testing__C109749__NRS-484B-253__motor_vehicle_driver/execution-manifest.json --case testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn --attempt .runtime-work/c109749-primary-compat-v9 --output .runtime-work/c109749-primary-saved-v3 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck` (`primary-saved.log`). It passed with preserved originals and nine joined frames. The fallback commands and logs are bound per candidate in `execution-manifest.json`.
- `diagnostic.json` is explicitly synthetic. Its nine frames, geometry and three-actor telemetry exercise processing shape and measurement code. The compact JSON is below the 2 MiB return limit. Its OpenDRIVE junction is a converter fixture, not a verified physical intersection. Black RGB frames do not establish traffic-light, indicator, actor, or junction visibility.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete` and `.venv-cpu/bin/python worker_check.py --complete` pass static checks (`assignment-static.log`, `batch-static.log`). Both strict assignment and batch commands fail with `Preparation acceptance failed: partial/missing packages remain` (`strict-assignment.log`, `strict-batch.log`). All 43 results remain partial. This is unfinished worker-owned CPU preparation, not an external blocker.

## Exact resume work

1. Complete semantic proposals and `proposals/semantic-index.json`; expand `case-plan.json` to every exact statutory branch and controlled comparison. Review the original NRS text, definitions, branch sources, accepted summaries and review context independently. Preserve uncertainty where accepted source bytes are absent.
2. Implement remaining exact case bundles, comparison-specific constructions and measurement contracts; keep linked comparison conditions fixed. Add the same three physical-risk candidates where policy and geometry are shared. Run exact offline, positive/negative compatibility and saved processing for each applicable case/candidate, rebinding hashes after changes.
3. Implement and CPU-test physical-completion/lifecycle fixture checks and independent delivery and comparison audits. They must reject missing evidence and verify fixed conditions and declared differences. Bind positive and negative diagnostic receipts without claiming physical acceptance.
4. Rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete --require-delivery-ready`, then the batch strict gate. Keep `result.json` partial until all CPU proofs pass. The separate timer handles Git; no Git command was run here.
