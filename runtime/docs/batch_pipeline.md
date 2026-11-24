# Autonomous batch pipeline

`pipeline.py` imports the existing JSON catalog unchanged and schedules actor-specific work using SQLite. Review is informational provenance. Judgment standards remain unknown until a separate designer labels recorded evidence outside this pipeline.

## Start from defined cells

Use Python 3.11+ for scheduling and the project CARLA interpreter for execution. All persistent inputs, state, logs and results belong under `../runs/scenario_pipeline`, configurable through `SCENARIO_PIPELINE_OUTPUT_ROOT`. Read-only `data/bootstrap` inputs are optional seeds; `init-inputs` never overwrites working snapshots. Fresh processing builds law templates from text and summaries instead of importing old declarations.

```bash
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite import \
  --catalog ../runs/scenario_pipeline/inputs/catalog/vocabulary_catalog.json \
  --summaries ../repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws/evaluation_scenario/scenarios.jsonl \
  --run example-001 \
  --worker '["/usr/bin/python3.11","/global/homes/m/msoroco/scratch/world-model-spec/scenario_pipeline/batch_pipeline/codex_bridge.py"]'
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite select --run example-001 --cell C353238 --limit 1
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite run --run example-001 --concurrency 2 --requests-per-minute 10 --timeout 900
```

Import does not make model calls; `run` does. Relevance batches cover full text and summaries without keyword-filtering away general duties. Templates and judgment observable requirements are shared per law/actor; bindings and cases are per cell/actor. A law missing its pre-extracted structure blocks affected work. Configured bridges read JSON from stdin and emit `{result,metadata}`; the included Codex bridge is invoked only when selected explicitly. Workers run read-only and do not independently write the shared library.

Existing run IDs cannot be overwritten. Use `resume` explicitly for the same inputs. Old declaration-based runs are unsupported; use fresh state and a new run ID. There is no compatibility, migration or label-profile subsystem.

## Shared templates and observable requirements

Templates preserve exact evidence, activation, obligations, exceptions, timing, numeric statutory thresholds and unresolved judgment phrases. `judgment_observables` attaches an `observable_requirements` object to each phrase/note entry. It contains only these lists:

- `observables`, `context_inputs`, `sweep_dimensions`, `recording_needs`: `{name,unit,description}`.
- `landmarks`: `{name,description,source,verification_evidence}` describing source-backed potential coverage anchors, with no selected value.
- `limitations`: what evidence or available capabilities cannot establish.

No rule, bound, formula, selected number or surrogate decision pattern belongs here. Intent is not directly observable. Factual/jurisdictional lookups stay authored world facts. Historical declarations remain in historical files and are not consumed.

SQLite serializes shared writes and retains template versions. Regeneration preserves observable requirements on matching phrase/note entries and rejects ambiguous matches or conflicting replacements. Dependent jobs consume exact versions. Model proposals cannot approve themselves; optional review status and timestamps do not gate scheduling or change semantic cache identities.

Bindings separate `direct` and `general_duty` base laws from conditional `context_refs`. Unattached independent facts never inflate the base variables. An explicit `--context` may attach a registry guard to a new run; ordinary physical observations for an active law do not attach unrelated contexts. Canonical quantities are deduplicated through `data/canonical_parameter_aliases.json`.

## Cases and fixed sweeps

Every case assigns all variables. `world_setup` is authored ground truth, `controller` is a requested target and `subject_behavior.value` is null until recording. Non-baseline cases target one law and carry comparison metadata. Assignments remain equal outside their declared differences.

Statutory thresholds retain linked below/at/above triples. Non-judgment plain rules retain compliant/violating attempt pairs, not verified outcomes. Any law containing judgment calls instead uses unlabeled physical sweeps, plus its statutory probes where applicable.

The cases worker returns `{cell_id,actor,status:"draft",cases:[ordinary cases],sweep_specs:[...]}`. It does not manually expand judgment cases. A complete sweep spec contains:

```text
sweep_id, target_law_id, judgment_refs:[{phrase,note}], status:"complete",
mode:"one_dimensional"|"joint", rationale,
axes:[{variable,observable,unit,min,max,spacing,
       measurement:{method,time_window,statistic},
       range_rationale,spacing_rationale,feasibility_evidence}],
landmarks:[{name,value,unit,source,verification_evidence,purpose:"coverage_landmark"}],
variable_assignments, recording_description
```

An unsupported plan instead has `status:"incomplete"`, its identity/rationale, and `missing_inputs`. Report it rather than invent capability. The axis changes a scalar authored fact or controller target; `observable` names the canonical physical measurement. `statistic` is min/max/mean/first/last for coverage reporting, not a legal predicate. Record the relevant window and retain the full time series.

Choose range from documented physical feasibility and verified landmark values, never from a supposed legal standard. Choose spacing from measurement resolution or meaningful increments. Prefer independent sweeps; joint grids need an interaction rationale. No unrelated Cartesian product is formed.

Deterministic code materializes all grid points, stable case IDs, the immutable spec version, and `selection_order`. Both endpoints are included; the terminal interval can be shorter. One-dimensional order is endpoints, midpoint, then breadth-first recursive bisection with lower-index tie breaking. Joint order is corners, center, then component bisection rank (maximum rank, sum, coordinates). No later labels, budgets or measured gaps alter the grid.

## Select and execute

No simulations are scheduled until selection is invoked. Without explicit case IDs, select the first three points per complete sweep; `--sweep` limits which sweep IDs participate. `--simulation-budget-per-sweep` changes the prefix length, never the grid. `--case` overrides sweep selection; `--limit` optionally caps total new selections.

```bash
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite select-simulation \
  --run example-001 --cell C353238 --actor motor_vehicle_driver \
  --sweep ACTUAL_SWEEP_ID --simulation-budget-per-sweep 3
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite run --run example-001 --stage construction --timeout 900
python3.11 pipeline.py --db ../runs/scenario_pipeline/state/judgment-sweeps.sqlite simulate \
  --run example-001 --python ../envs/carla-py38/bin/python --host 127.0.0.1 --port 20000
```

Provide simulator documentation or `--simulator-context` at import for offline feasibility planning. The construction surveys resources and preserves physical causes named in the law, all held facts, the selected actor and recording description. It exposes `--check` for offline checks. The executor locks the actual server process, runs static checks first, then one recorded invocation per attempt. It does not launch a server or perform structured scene-graph extraction.

Failed and interrupted execution evidence is retained. Failed attempts consume budget and are not automatically retried, including expired execution leases. Repeating selection or resuming does not fill gaps or select later points. Explicit further selection is available. Semantic transient failures still receive bounded retries; `--retry-failed` does not reset execution jobs.

## Reuse constructions and execute on several engines

Construction workers receive all frozen members of a linked comparison/sweep, scoped to the same cell, actor and target law. An optional `reuse_contract` declares `group_version`, `supported_case_ids`, `config_file` and `capabilities`. The JSON configuration contains the exact `cell`, `actor` and `case`. The runner must actually read that configuration and support every declared member's branches and recording requirements. Compatible members reuse the frozen source bundle and change only those configuration fields; unsupported members use independent model construction. A per-group lock prevents simultaneous first constructions from wasting model calls. Reuse records source artifact, implementation and specification versions. No geometry or actor substitution is permitted.

Pass a JSON array to `simulate --engines PATH`, for example:

```json
[
  {"id":"gpu-a","ssh":"ALLOCATED_NODE_A","python":"/absolute/carla-env/bin/python","host":"127.0.0.1","port":20000},
  {"id":"gpu-b","ssh":"ALLOCATED_NODE_B","python":"/absolute/carla-env/bin/python","host":"127.0.0.1","port":20000}
]
```

Omit `ssh` for a local engine. An explicitly user-authorized dedicated login-host engine can set `"allow_login_node": true`; the default remains false. This opt-in does not establish resource sufficiency or ownership. Source, environment and output paths must be accessible on each node. Servers must already be running on user-provided dedicated compute resources. No allocation, launch or sustained login-node simulation is performed. Preflight records GPU/memory/load snapshots; these are observations, not resource reservations. A missing engine is reported without stopping reachable engines. Two entries reaching the same actual listening process are rejected, even under different host aliases. OS locks are keyed by node boot, PID and process start time and shared across coordinators; SQLite leases are held by the coordinator only. Workers never open the database.

```bash
python3.11 pipeline.py --db DB simulate --run RUN --engines ENGINES_JSON --timeout 900
```

The old `--python ... --host ... --port ...` single-engine interface uses the same scheduler. Each engine handles one attempt at a time. Timeouts stop the worker's own runner process group; uncertain transport/termination leaves that actual server unavailable while other engines continue. Restart an uncertain dedicated server before scheduling it again; a new process has a new identity. Do not clear a lease merely because an SSH command exited.

After files close, `result.json` is atomically sealed with attempt, case specification, configuration, implementation, runtime and artifact hashes. There is no separate completion receipt. Recovery verifies these bindings, measurements and complete evidence before adopting an interrupted result, without driving again. Exit success or an unsealed `result.json` is insufficient. Incomplete attempts remain diagnostic evidence. A controller correction leaves completed unaffected recordings intact; active jobs finish their frozen bundle. A diagnosed correction with a reusable contract automatically versions compatible, constructed, never-driven siblings; already-started members are retained and listed for impact assessment in the event log. Pending construction jobs use the current anchor when built. Completed affected work needs a separate diagnosed changed attempt. A substantive frozen-specification change needs a new specification version, and export rejects a definition that differs from its executed specification. Use the existing runtime-edit coordination for shared helper changes; never modify helpers beneath active executions.

For delivery after the pool finishes, use `run_selected.py --recorded-only --actor ACTOR` with the existing library and validator arguments (see [delivery workflow](delivery_workflow.md)). This reuses existing conversion/review tooling and cannot select, construct, drive or repair cases. Case acceptance registers canonical recordings; finalize the frozen law set once using `pipeline.py finalize-set --set SET`. Source attempt history stays in the run; no new postprocessing service or labeling stage is introduced.

## Recording contract

Every ordinary case and complete sweep has:

```text
recording_description:{
  channels:[{name,unit,sampling_rate_hz,method,time_window,reference_frame,uncertainty}],
  context_inputs:[{name,unit,method}], limitations:[string]
}
```

It must cover the targeted judgment's observable/context requirements. Construction preserves this description exactly. Besides existing measurements, target checks, physical-event flags, trace/video references and frame maps, execution `result.json` provides:

```text
recording_description,
recording_evidence:[{name,unit,reference}],
realized_observables:{name:{value,unit,method,time_window,statistic,
                           sample_window_s:[start,end],reference}}
```

Each temporal evidence reference points to JSONL `{time_s,value}` samples at the declared rate. Context references point to JSON objects keyed by context name. Missing channels, units, values or rates make evidence unconfirmed and retain the failure. Sweep summaries must match their frozen method/window/statistic and recompute from saved samples. Requested setpoints never substitute for measurements. Position/heading/speed trace, videos, frame mappings and hashes are still required.

Record required raw observations and instance geometry, grade, friction inputs, weather, obstruction geometry and participant states, with stated uncertainty. Videos alone are not assumed sufficient for numerical predicates. Finite recordings cannot promise every imaginable predicate or proof of an interior mental state.

## Outputs and progress

New run administration, semantic outputs and logs live under `runs/scenario_pipeline/state/operations/<run-id>/`. Frozen inputs belong in `inputs/`, original attempts and canonical evidence in `recordings/`, and accepted review outputs in `work/`. Use the CLI and path helpers to resolve exact locations; historical pilot layouts and one-shot entry points are retired.

`status` and `export` provide stage counts, token usage when reported, exact input/review provenance and dependency state. `sweep_coverage.json` and `progress.html` expose each frozen spec, planned/selected/unselected counts, failures, realized values, gaps, raw evidence references and video links. Joint measured points are retained separately from marginal coverage. Unselected points are not failures; missing measurements are not replaced by requested values. Reporting never triggers runs or adapts sampling.

No legal verdict is emitted. Non-judgment attempt labels identify test intent only. Later threshold choices, legal predicates and video labels belong outside this pipeline.

Use the import, selection, semantic processing, construction, and execution commands above. Saved trace conversion uses `adapt-trace`; see [traffic_spec_adapter.md](traffic_spec_adapter.md).

## Restricted-law runs and downstream few-shots

`import --laws path/to/laws.jsonl` restricts relevance and downstream law processing
to exact law IDs/texts already present in the catalog. The catalog and cell IDs stay
unchanged. `--fewshots path/to/fewshots` freezes indexed example excerpts for cases
and construction in `inputs/run_inputs.json`; those snapshots participate in job
identities. Example measurements and legal standards are never current-run facts.

Opted-in runs record judgment-sweep completion acceptance: only frozen
one-dimensional endpoints may have an incomplete physical maneuver, at most one
attempt at each endpoint; every interior case must complete. Missing samples remain
pending, and failed attempts remain visible. No endpoint redefinition or gap filling.

`run_selected.py --db DB --run RUN --cell CELL ... --python CARLA_PYTHON
--library TRAFFICSPEC_LIBRARY --validator VALIDATOR --port PORT` processes every
generated case sequentially and validates each cell's first capture before advancing.
It requires completed semantic case sets and a dedicated live CARLA server. It never
launches a server or automatically retries driving attempts.

Generic constructions use `scripts/pipeline_capture.py`: original-run telemetry,
recorder data, base/abstract graphs, and adapter evidence are captured after each
owned tick, without another driving episode. Native maps and real control actors
are preserved. Speed, stop, and signal cells require device governance in the final
JSON; signal cells additionally require observed indications for every frame.

The sequential driver restricts both construction claims and execution claims to
the selected case. `--cell-run CELL=RUN` selects an explicitly authored context
variant, and `--cell-inventory CELL=PATH` supplies verified native resource evidence.
The first-case gate requires a complete original capture, decoded trace and actual
required controls. Engineering target failures and unknown setup fields remain
failures in `delivery_index.json`, even when the capture gate passes. A recovered
valid original capture is reused; it does not request another driving episode.

Completion reports include executions from superseded constructions that consumed
the same frozen sweep specification. Endpoint allowance counts all their retained
attempts. Changing construction versions cannot clear a physical failure. The
adapter retains native junction geometry, opposing-lane centerlines and painted map
objects with explicit source and uncertainty; these do not establish a legal entry
boundary or geographic law classification.

`run_selected.py --case ID` restricts execution to new frozen points in one cell.
It requires an already validated original capture for that cell and keeps the full
planned case set and existing failure/capture entries. It cannot silently repeat
an older successful clip or truncate the full plan.

## Current delivery contract

The reusable delivery, runtime-edit, and diagnosed-repair workflows are documented in [delivery_workflow.md](delivery_workflow.md). Primary videos cover the complete delivered trace; previews are optional. Baselines are definitions unless explicitly selected. Fixed judgment grids are unchanged by physical/capture repairs, and actual judgment sweeps remain unlabeled. Repair execution and publication use the same run and one authoritative export directory.

## Canonical storage

See [storage.md](storage.md) for the single recording store, explicit end-of-set finalization, optional packaging, and current review navigation. Case processing does not consolidate or export datasets.
