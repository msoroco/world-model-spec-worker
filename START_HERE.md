# Full demo-test delivery preparation

Update 011 uses `runtime/main-pipeline-v6` and return branch `worker/demo-test-full-delivery-v2`. Read `DELIVERY_CONTRACT.md` first. Every selected case needs a primary and at least one tested physical fallback. Supply and CPU-test the exact canonical preparation, execution, saved-processing, audit, and acceptance commands. Preserve existing case IDs and comparisons. The worker does not use CARLA, NERSC or campaign SQLite.

Start from updated `main`. Fetch `worker/demo-test-full-delivery-v1` at commit `43af39a1cd5d231d9c71d2d855e206fc2dd57043` and restore only its `work/` subtree as editable CPU preparation. Do not merge its old batch, runtime, notices or proofs as current authority. Replace the `runtime-v3.py` and `sitecustomize` workaround with ordinary root launchers. Re-run all exact proofs under v6.

The operator starts this agent manually. Use Python 3.11 or newer; create an
ignored `.venv-cpu` and install `runtime/main-pipeline-v6/requirements-cpu.txt`.
Software compatibility also needs FFmpeg and the Lean `lake` toolchain pinned
by the exported library. Record a precise dependency blocker if either cannot
be installed. Read `batch.json`, its four partitions,
`skills/worker-preparation/SKILL.md`, the exact assignment inputs and
`references/catalog.json` and `examples/measurement/README.md`. Use up to four
assignment owners, one per partition. Complete one representative exact case
through the new gate before expanding the remaining partitions.
Run `python3.11 reference_select.py ASSIGNMENT_ID` to find matching
accepted source examples; read their hashes and limitations before adaptation.
The batch uses the current `demo-overlap-v3` law split as its only authority.
Do not read or reconcile older split versions. The lead alone integrates shared changes, validates, commits and pushes the
configured return branch. Use existing accepted implementation references; do not infer coverage from earlier trial status. Do not run CARLA, NERSC tools or the main campaign database.

Read FULL_BRANCH_CONTRACT.md and references/v6-capability/index.json before building cases. The v6 files are source-hashed CPU implementation seeds; adapt them and rerun every proof. Complete all statutory branches and comparisons for every law; a first capability case does not finish the assignment.

For every assignment, read the law, selected witness, cell, actor and prior
evidence. Complete the selected branch first. In `case-plan.json`, set
`selected_branch` to the exact `assignment.json.branch` and list
`requirement_dispositions`. Each row needs `requirement`, `source`, `status`
(`selected_required`, `alternative_pending` or `exception_pending`) and
`evidence_or_gap`. An officer/signal exception does not force a positive
demonstration in a base case; establish absence of actual governing control.

Build exact cases, connected road geometry, controllers, cameras, complete
capture channels, a measured-results finalizer and CPU tests. Use the
source-hashed accepted training implementations as adaptation examples, never
as test evidence. Check topology, routes, signs/markings, participants, camera
configuration and duration offline. Record assumptions that offline tests cannot establish in the required case fields. A law-specific measurement cannot be replaced by a
generic speed or source-presence check.

Use `worker_exchange.capture.PROFILE` for every exact case: one 1920×1080
overview and three 1280×720 detail cameras at 20 Hz. Put the four named
camera configurations in `config.json.cameras` in profile order. Each needs
`name`, `width`, `height`, `fov_deg` and a concrete `pose_strategy`. Put
`camera_plan` in `case-plan.json` with the profile version, exact `duration_s`,
`composition: synchronized_four_view_primary`, and `coverage` rows naming
`subject`, `interval` and `view`. The runner must capture all four views on
the same original ticks, retain individual sources and compose a synchronized
primary `raw.mkv` with the supplied `worker_exchange.media.compose_four_views`
helper and the original `video_frames.jsonl` map. Store its source-hashed
receipt with the capture. Keep full startup, approach,
interaction, clearance and final observation. Offline plans establish intended
coverage; do not claim measured pixels or duration adequacy from offline plans.

For **each exact case**, write a `worker-measurement-contract-v1` JSON file.
Its `requirements` list has one row for every `selected_required` disposition
in `case-plan.json`, identified by `disposition_index` and the exact
`requirement` and `source` text. Each row needs a distinct `output_key`, a
function `method` defined in the saved finalizer, `kind` (`measured` or
`sourced_context`), `value_type` (`number`, `boolean`, `object`, `array`, or
`text`), and nonempty `inputs` naming actual fixture files. The finalizer's
`analysis-report.json.measurements[output_key]` must contain a concrete
`value`, the same `method`, and `sources` mapping each input path to its
SHA-256. Put unresolved physical or legal conclusions in separate limitations;
do not use `pending`, `unknown`, or an empty value as a measurement.

Give each case a `worker-fixture-recipe-v1` JSON file with `base` set to
`runtime/main-pipeline-v6/fixtures/retained-speed` and text `additions`
(`path`, `source`, `sha256`) from that case's `work/` directory. The contract's
recipe must set `remove` to `["case.json","config.json","result.json"]`
to remove the retained example's outputs before the case's code runs. The contract's
`negative` object names one case-specific file in `remove` and an
`error_contains` string of the form `Missing required source: <path>`. The
finalizer must raise that error when the file is missing. Use the shared base
for converter testing, and the additions to exercise the case's actual
measurement. The case fixture remains a diagnostic, never physical evidence.

`source_observation_terms` are law-evidence prompts, not Core IDs. Map every
term to actual acquisition in `case-plan.json.source_observation_mapping`.
`config.required_atoms` contains only pinned ontology IDs. Conditional atoms
must declare `config.source_packets`: `scenario_geometry` for one-way roadways
or medians; `scenario_geometry` plus `scenario_rule_evidence` for an
original-frame verified regulatory sign; `environment_calibration` plus
`surface_provenance` for measured visibility or authored ice/snow. Diagnostic
fixtures must contain these packets and converter coverage must pass. The
source declaration alone is not evidence of realized physical behavior.

If a portable adapter/capture/validation defect blocks the selected branch,
place source-hashed replacement Python files and `overlay.json` under
`work/_shared/runtime-overlay/`. See `overlay.py`; materialize with
`python3.11 overlay.py` and test the effective runtime. Keep the
pinned baseline and Core ontology unchanged. Source-hash and test every
overlay against the pinned runtime.
The v6 baseline already contains the reviewed v5 adapter repair. Do not copy
the v5 overlay or any returned v5 package into this fresh batch.

For every exact nonbaseline case, run `runtime.py offline` and store a hashed
log in its execution-manifest `offline` entry: `command`, `exit_code: 0`,
`log`, `log_sha256`, `construction_sha256`. Add `measurement_contract`,
`fixture_recipe`, and `native_handoff` to each manifest entry. The handoff has
`python_env_var: CARLA_PYTHON`, `host_env_var: CARLA_HOST`, and
`port_env_var: CARLA_PORT`. Run `runtime.py compatibility-recipe` against the
exact case and a temporary ignored `.runtime-work/` output. Copy only its
small compatibility receipt, analysis log, and negative log into the case's
`receipts/` directory; bind their hashes in the manifest. A partial
package still needs executable, offline and compatibility proofs; use
`blocked` only for a precise, test-backed CPU barrier. Diagnostic fixtures
prove software compatibility, not physical behavior or legal compliance.

The first GPU command in `result.json` must use local `execute-delivery`
for one exact canonical job, with `--job "$JOB_ID" --db "$DB" --run "$RUN"`
and `--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"`.
The command uses run and job placeholders returned by `prepare-delivery`.
Portable `runtime.py capture` remains diagnostic; it is not the delivery launcher.
Do not use the worker CPU environment as Native Python or hardcode a host.

Commit source, small text fixture additions, tests, handoffs, receipts, and
logs. Keep diagnostic videos, decoded frames, graph files, converted traces,
and generated fixture trees in ignored `.runtime-work/`. The return gate rejects
binary media and oversized generated trees under `work/`.

Run the full runtime selftest, including negative fixtures, assignment tests,
every exact-case offline check and every compatibility check. Copy its
`verification.json` and log into `work/_shared/`. Write
`work/_shared/runtime-proof.json` with `format: worker-runtime-proof-v1`,
`runtime_manifest_sha256` (effective runtime), `command`, `exit_code: 0`,
`log`, `log_sha256`, `verification_receipt` and `verification_sha256`.
Run `python3.11 -m unittest discover -s tests -p test_entrypoints_current.py`.
The gate must run without a bootstrap `PYTHONPATH`. All-empty candidate lists
and queues lacking canonical local job commands fail under update 008.

```sh
python3.11 worker_check.py --complete --require-delivery-ready
```

If the gate fails, continue repairing worker-owned code and proofs. Commit and
push the return branch after the strict gate passes. Report the commit, case and
fallback counts, exact CPU proof hashes, and any remaining worker-owned blocker.
Do not describe downstream execution tasks or claim physical acceptance.
