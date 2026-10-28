# Migration to the shared main runtime

Start a fresh agent session on worker/demo-test-runtime-migration-v1 from updated main. Preserve worker/demo-test-preparation-v2. Never inherit its readiness labels. migration-candidates/ contains selected scenario-specific source from 077a9dd, with provenance; reuse only after review. Do not restore the old capture/conversion/check infrastructure.

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
