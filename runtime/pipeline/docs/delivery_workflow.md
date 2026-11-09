# Current recording and delivery workflow

Run `run_selected.py` with the existing database/run, selected cells, dedicated CARLA endpoint, compatible SDK interpreter, TrafficSpec library, and decoder. It executes cases sequentially, adapts original captures, checks measured scenario expectations, and renders full reviews. Baselines remain definitions unless `--include-baselines` is supplied. Semantic construction jobs do not drive the simulator.

For parallel execution, select cases and complete construction with `pipeline.py`, then run `simulate --engines ENGINES_JSON` (see [batch guide](batch_pipeline.md)). Finalize those selected recordings without any construction or driving:

```sh
python3.11 run_selected.py --db DB --run RUN --cell CELL --actor motor_vehicle_driver \
  --recorded-only --python CARLA_PYTHON --library TRAFFICSPEC_LIBRARY --validator DECODER
```

Repeat for each selected actor. This mode verifies the sealed original result, adapts its captures and renders the existing full review. Pending or failed execution jobs stay pending/failed, and unselected plan members are listed explicitly. It never selects further points, calls a construction worker, schedules a repair, or drives again. Conversion or evidence failures remain unresolved; original attempt evidence is retained. Existing review tooling must support the constructed capture format; unsupported recordings are reported rather than coerced into an accepted pair.

## Repair affected cases without stopping independent work

Missing capture/evidence, incomplete realization, unmet targets, and unintended deterministic outcomes require diagnosis and a changed construction. The configured semantic worker receives retained attempt evidence, the prior construction, and the unchanged approved case. Its repair proposal identifies the cause, evidence references, actual changed files, allowed engineering scope, and the approved-case hash. Repaired executions also report the exact requested world/setup and controller assignments for validation. Only then does the normal executor run a new internal attempt.

`--max-repairs` defaults to two diagnosed repairs per case. Failed attempts and their measurements remain available; the case identity and run stay the same. Exhausted or out-of-scope repairs remain unresolved, while other cases continue. The agent investigates remaining causes and asks only when a necessary repair exceeds existing authorization. An unchanged construction is not replayed for a favorable label. Fixed sweep endpoints, spacing, and approved target values remain unchanged. `pipeline.py simulate --max-repairs 2` performs physical/capture repairs; end-to-end adaptation and expected-label checks use `run_selected.py`.

## Coordinate changes to shared code

A run records hashes of pipeline, adapter, capture-helper, and graph-generator dependencies. Configure extra file paths in `simulator_context.runtime_dependency_paths`; a non-default capture helper can use `capture_requirements.helper_path`. Construction and execution use a shared runtime lock and verify hashes before and after their work. Uncoordinated changes are rejected and their diagnostics retained.

An intentional repair uses one current implementation:

```sh
python pipeline.py --db <database> runtime-edit --run <same-run> \
  --reason 'Correct capture-helper timing' \
  --edit-command '["python", "<repair-script>"]' \
  --python <CARLA-python> --library <TrafficSpec-library> --validator <decoder>
```

The exclusive lock waits for active work before the edit. Changed hashes and reasons are retained internally, and affected cases are rerun, adapted, and validated within the existing run. All selected executions are invalidated by default. Use repeated `--case` only when evidence establishes the narrower impact. The same capture requirement source is updated when its helper changes. No implementation copies or duplicate user-facing run directories are required.

## Review exactly what Lean receives

`review_recordings.py --output <run-directory>` renders a primary review covering every delivered trace frame. Optional `--previews` creates separate focused clips. Primary coverage is enforced even when an engineering target-attainment window is much later than the turn or sign approach. No violation is removed to repair a compliant case.

Expected labels describe measured scenarios under declared assumptions wherever the selected rule applies throughout the delivered trace. They do not evaluate a law formalization. A target-attainment window measures controller performance and is highlighted separately. Actual judgment sweeps have no expected label. Speeds are stored in m/s and reported with explicit units. The default speed triple uses ±5 mph outer margins and a middle command 0.5 mph inside the compliant side; justified overrides are recorded.

Posted-speed acceptance verifies the selected native sign, posted value/unit, lane identity, measured approach/passage, subsequent governed-portion coverage, and clearance from unrelated signal controls. Authored governance is explicit and is not inferred from graph presence. Existing signal and stop-label checks verify actual indications and the selected signed footprint/reference geometry.

## Finalize once per selected law set

Accepted pairs live in the canonical `recordings/<recording-id>/` directories.
Case processing updates only run-local status and acceptance. Define a frozen
selection and, when every selected member has a disposition, run:

```sh
python3.11 pipeline.py finalize-set --set SET_ID
```

This writes set metadata and verifies evidence without copying recordings. A
portable copy is optional: `pipeline.py package-set --set SET_ID --output PATH`.
Add `--zip` only when an archive is needed. See [storage.md](storage.md) for the
layout, selection schema, migration, and completion semantics.

## Validation

The pipeline CLI uses Python 3.11+. Run the repository unit tests with `python -m unittest discover -s tests`. FFmpeg tests exercise actual encoding and cache invalidation. SDK-dependent graph/visibility tests additionally run with the installed CARLA interpreter and `scenario_pipeline` plus `third_party/carla_scene_graphs` on `PYTHONPATH`; they are skipped when that SDK is unavailable. Unit fixtures and saved delivery checks do not launch a simulator or rerun a driving episode.
