# Migration to the shared main runtime

For update 004 the initial migration started on worker/demo-test-runtime-migration-v1. For update 005 continue that same branch after merging origin/main; follow the section below. Preserve worker/demo-test-preparation-v2. Never inherit its readiness labels. migration-candidates/ contains selected scenario-specific source from 077a9dd, with provenance; reuse only after review. Do not restore the old capture/conversion/check infrastructure.

## Setup and proof

Use Python 3.11, FFmpeg/ffprobe on PATH, and the Lean version pinned in runtime/main-pipeline-v1/library/lean-toolchain (install through elan if necessary). No CARLA Python package is needed for these CPU checks.

```sh
python3.11 -m venv .venv-cpu
.venv-cpu/bin/python -m pip install -r runtime/main-pipeline-v1/requirements-cpu.txt
.venv-cpu/bin/python runtime.py verify --runtime runtime/main-pipeline-v1
.venv-cpu/bin/python runtime.py selftest --output .runtime-work/proof --lake "$HOME/.elan/bin/lake"
.venv-cpu/bin/python worker_check.py
.venv-cpu/bin/python -m unittest discover -s tests
```

Use a new output directory on each selftest attempt; retain failed logs. selftest builds the actual Lean decoder, converts retained source data with mandatory-observation checks, renders and decodes the video, runs exported regression tests, and rejects corrupt fixtures. This three-frame diagnostic subset is not a complete maneuver or visibility proof. Do not run main-repo comparison mode here: the upstream repo is intentionally absent. Host CPU libraries and FFmpeg are required; log a precise installation problem rather than replacing checks.

## Implement the six preparation steps

First complete testing__C109705__NRS-484B-400-2a__motor_vehicle_driver as a pilot. Read exact supplied law/witness/context; define intended cases; implement the intersection builder, actual vehicle controllers and cameras; add scenario geometry/channel/file-format checks; run all CPU checks; return a runnable package explicitly distinguishing unverified motion/visibility/duration from implementation omissions. Then process all four partitions with at most four independent owners, integrating shared changes through the lead. Each owner edits only its assignment directory. Only the lead commits/pushes.

Use the six scenario skills for substantive law and evidence rules and skills/worker-preparation for worker routing. Read runtime/main-pipeline-v1/capabilities/ before claiming a missing feature. Historical examples demonstrate interfaces and methods; their cell geometry, controls and evidence do not transfer automatically. Preserve public-way/device-authorization assumptions as explicit synthetic context, separate from measurable physics.

Do not recreate capture, graph projection, Core conversion, encoding, decode receipts, or shared validators. Reuse these exported implementations:

| Task | Shared implementation |
| --- | --- |
| Capture original frames/states/all actors | python/pipeline_capture.py; scene_graph_collector.py; original_observations.py |
| Stage contracts and sweep expansion | runtime.py validate-stage; runtime.py expand |
| Materialize and offline-test exact cases | runtime.py materialize; runtime.py offline |
| Source validation | runtime.py validate-native; worker_exchange/media.py |
| Saved Core conversion and Lean | runtime.py process; runtime.py build-decoder |
| Saved video composition | runtime.py render |
| Reusable motion/geometry/signal checks | exported batch_pipeline and capability catalogue |

Read each --help and source signature. Construct runner.py with --check and --output-dir PATH --host HOST --port PORT. Host/port identify an already running simulator supplied later by the local operator; they convey no NERSC knowledge. --check/tests must never connect to a simulator. Use lazy CARLA imports. Keep scenario-specific code in bundle files and add analysis code for capability results. Shared runtime extensions belong under work/_shared with tests and an explicit proposal; never shadow frozen modules.

Reuse one source decode receipt for frame counts and pixel checks when its source SHA and checker version match; retain distinct final encoded-video validation. Do not replace original state checks with image guesses. For future cameras start with a 1920x1080 overview and three 1280x720 detail views, with configurable framing; physical visibility remains unverified until capture. Never change completed recordings.

## Required execution handoff

Keep the existing result.json/proposals/HANDOFF schema enforced by worker_check.py. In addition every ready assignment needs execution-manifest.json (worker-execution-manifest-v1): assignment_id, runtime_manifest_sha256, and cases[]. Every nonbaseline expanded proposal case must appear once; baseline-only and unexpanded sweeps are rejected. Each entry has case_id, kind (capability or delivery), construction (relative assignment path), and construction_sha256. Its construction is the ordinary main-pipeline construction JSON with inline files; config.json freezes that exact selected case. Capture contract must equal the proposal recording_description. See exported worker_exchange/execution_manifest.py and tests/test_runtime_handoff.py for executable schema examples.

Capability entries also require measurement_procedure with entrypoint (existing relative analysis script) and output_schema. Implement the measurement, decision/report generation and follow-up configuration code now; a statement that GPU measurements are unknown is insufficient. Capability-ready means the executable discovery experiment is ready, not that a delivery sweep is frozen. Set result readiness_kind to capability or delivery_prepared. Provide exact per-case offline commands and hashed logs; exercise all cases, not one baseline. Never call unimplemented code a physical blocker. A genuine external asset blocker must identify the missing asset, attempted alternatives, and the exact capability it prevents; continue other work.

For example:

```sh
.venv-cpu/bin/python runtime.py offline --manifest work/ASSIGNMENT/execution-manifest.json --case EXACT_CASE --output .runtime-work/EXACT_CASE
```

No simulation runs here. Locally the main worker_exchange prepare-jobs/adopt-case commands validate the same manifest, freeze a fresh child revision and create exact pending jobs without dispatch. Local ownership/resource checks and physical acceptance stay local. Do not write SQL or reconstruct campaign paths.

## Completion

Run worker_check.py --complete --require-ready, all per-case offline checks and assignment tests. If genuine external blockers prevent full readiness, run submission validation separately, record the failed preparation-acceptance result and precise blockers; do not stop for implementation defects that can still be fixed. Provide work/_shared/lead-acceptance.json with per-assignment commands, logs, readiness kind and unresolved physical checks. Commit and push worker/demo-test-runtime-migration-v1 using the existing default Git identity. Do not start another agent session or simulation automatically.


## Update 005: direct output and package-specific compatibility

Preserve the existing 22 packages/65 cases at 8ca64e0. Merge origin/main on the current return branch, retaining uncommitted work through a commit first if needed. Do not force-push. Generic selftests and the previous ready labels do not qualify packages under the stronger gate. Result acknowledgments must advance to applied_update 5 after repairs.

### Reuse these helpers in the actual runner and analysis

- `worker_exchange.native_output.FrameMap(path)` is a context-managed original frame writer. Call `append(frame, original_time_s, **extra)` exactly once per recorded tick. It writes video_frame, carla_frame, native_frame and time_s, rejects reversed/duplicate frames and never overwrites a file. Use it at capture time; do not rename or reconstruct identities in saved evidence afterward.
- `worker_exchange.native_output.write_result(attempt, result)` validates and creates the native execution result. The assignment's `analyze.py --attempt PATH --output REPORT` must compute actual measurements and call it. Unknown physical causes/setup/motion remain false or pending; no fabricated target matches or legal verdicts. The worker's preparation result.json in its assignment directory and the future recording attempt's native result.json are different files.
- `worker_exchange.world_restore.snapshot(client)` before map changes, and `restore(client, saved)` after owned actor/encoder cleanup, handle packaged and generated worlds and verify map/settings/weather readback. Save that receipt. Ensure failures in one cleanup action cannot skip remaining cleanup/restoration; add client-double tests for both world kinds and failed readback. The local owner retains responsibility for server/resource closure.
- `worker_exchange.environment_acquisition` is the retained production RGB/instance contrast-range and authored surface provenance method. See capabilities/environment for its exact original caller and provenance. Adapt the original geometry/material assumptions explicitly; its surface helper describes the original dry asphalt scene and dimensions. Query actual native material inventory/paths rather than copying historical absolute paths. Calibrate before the recording interval, then pass same-frame environment_measurements through PipelineCapture.capture(extra=...) as shown in the retained caller. Do not treat named channel dictionaries, ClearNoon, precipitation or absent snow appearance as these measurements.

### First run the supplied software example

After installing the existing CPU requirements, build the decoder once:

```sh
.venv-cpu/bin/python runtime.py build-decoder --library runtime/main-pipeline-v1/library --output .runtime-work/decoder005 --lake "$HOME/.elan/bin/lake"
.venv-cpu/bin/python runtime.py compatibility-example --output .runtime-work/output-example005
.venv-cpu/bin/python runtime.py compatibility --manifest .runtime-work/output-example005/execution-manifest.json --case diagnostic__output_contract__case --fixture .runtime-work/output-example005/fixtures/retained --output .runtime-work/output-example005-processed --library runtime/main-pipeline-v1/library --validator .runtime-work/decoder005/.lake/build/bin/adapterCheck
```

Use fresh paths on retries. The example executes actual bundled analysis followed by existing native validation, mandatory-observation conversion, Lean decoding, rendering and final full decode. It preserves incomplete maneuver/unknown physical-cause flags. It uses an explicitly adapted three-frame diagnostic subset, not new evidence. Read the generator and analysis in worker_exchange/compatibility_example.py; do not copy its speed-only requirements into other assignments.

### Repair the pilot, then all packages

Every exact execution-manifest entry must now include:

- `measurement_procedure.entrypoint`: the actual bundled analysis/finalization script, also for delivery preparation.
- `acquisition`: mapping every required_atoms entry and recording channel name to `{entrypoint, method, evidence}`. entrypoint names an actual bundled source file. method describes its measurement/acquisition and evidence lists retained output references. No requirement deletion or weaker renaming to make tests pass.
- `compatibility`: `{receipt, sha256, fixture, log}`. receipt and log are paths relative to the assignment directory. fixture is a contained **repository-relative** path, so cases may share diagnostic fixtures under work/_shared/fixtures/. sha256 binds the generated compatibility.json receipt. Copy the generated compatibility-analysis.log alongside it.

Create small diagnostic acquisition fixtures for each distinct runner/analysis implementation, including required actors, channels, joins and source context. Exercise every exact case configuration through `runtime.py compatibility` using its real construction and analysis. Fixtures must contain acquisition data, not result.json or analysis outputs, and cannot shadow bundled configuration/implementation. Keep fixture provenance explicit; synthetic actor/motion records are software tests only. Preserve the existing generic retained-data selftest as a separate shared-runtime check. Binary diagnostic assets are supported under the existing 2MiB-per-return-file cap; reuse shared fixtures rather than copying payloads per case.

The command derives request identity/case settings from the frozen package, rejects analysis changes to original acquisition or implementation/configuration, reuses source decode receipts, and separately decodes the final video. Its receipt binds case, full construction, runtime, actual analysis, fixture and analysis log. Copy only small receipts/logs into results; retain your fixtures in Git. Do not copy generated delivery videos as worker outputs.

Add negative tests for missing native result, missing carla_frame, missing environmental acquisition, changed hashes, missing channels and incomplete motion. Include tests of actual capture-side writer calls using client/sensor doubles; do not claim these prove physics or framing. Genuine unsupported mandatory observations must be reported precisely as blockers rather than fabricated or silently waived. Preserve separate submission validation and preparation acceptance in that event, and continue all independent implementable repairs.

Run all exact-case offline checks and compatibility checks, then `worker_check.py --complete --require-ready`. Update lead-acceptance.json with per-case commands, hashed logs, compatibility receipt locations, acquisition coverage, restoration test results and remaining physical checks. Commit and push the same return branch. No CARLA run, canonical acceptance or statutory completion is claimed. The operator initiates this continuation manually.
