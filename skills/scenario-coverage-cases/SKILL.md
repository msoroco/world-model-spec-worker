---
name: scenario-coverage-cases
description: Build actor-specific statutory boundary probes, non-judgment attempt pairs, and fixed physical sweeps for judgment-call laws from cell bindings. Use for step 4; never define a judgment standard, label an actual judgment sweep, select new laws, or execute scenes.
---

# Scenario coverage cases

Read the requested cell, its bindings, active actor-specific templates, shared observable requirements, and available simulator resource documentation. Start from the existing catalog without rebuilding cells. Keep fixed layout, maneuver, control, and actors separate. Use only active `law_refs`; unattached context laws must not inflate base variables.

## Choose the appropriate coverage

Provide one neutral baseline definition per actor; do not simulate it by default. Explicit `--include-baselines` selection enables baseline execution. Each other case targets one law; incidental effects on other laws are expected. Preserve activation branches, exceptions, and timing without claiming they occurred in a run.

For every explicit statutory numeric threshold, keep linked below/at/above probes with the threshold reference, operator, units, and justified epsilon. A posted limit is an authored fact, not a judgment standard. These probes remain required when the law also contains judgment calls.

For a law without judgment calls and without numeric thresholds, keep a linked `compliant_attempt` and `violating_attempt` with the activation genuinely possible in both. These are intended tests, not verdicts. A deterministic probe within a law containing judgment phrases may carry an expected scenario outcome only when its other conditions are explicitly fixed as synthetic assumptions; actual judgment sweeps remain unlabeled.

For each judgment phrase, return a fixed `sweep_specs` entry, not a qualitative safe/unsafe pair. The phrase remains unresolved. Use the law's observable requirements and document the underlying physical quantity, units, range, spacing, controller-to-observable mapping, and measurement window/statistic. Range comes from documented vehicle capability, geometry, simulator limits, and verified landmarks; landmarks anchor coverage, never define a legal threshold. Spacing comes from measurement resolution or meaningful physical increments. Never adapt either to a later judgment choice or execution budget.

Prefer independent one-dimensional sweeps with other inputs fixed. A joint grid needs an explicit reason why interacting dimensions matter and a visible case count. Do not enumerate unrelated variable combinations. If capability, geometry, or a required recording channel cannot be established, return an incomplete sweep with `missing_inputs` rather than invent feasibility.

## Freeze and isolate the plan

Return compact sweep specs and shared full variable assignments. Deterministic `batch_pipeline/sweeps.py` expands the grid, generates stable case IDs, and freezes its version and coarse-to-fine selection order. Include both range endpoints; the final interval may be shorter than the declared spacing. No grid refinement or gap-filling runs follow downstream labeling choices.

Each complete spec carries `sweep_id`, target law, exact judgment refs, mode, axes, physical feasibility evidence, range/spacing rationale, sourced landmarks, full assignments, and recording description. Each axis names the authored/controller `variable` and measured `observable`; its measurement specifies method, time window and one of min/max/mean/first/last for coverage reporting. These summaries are not a legal predicate; retain the entire raw stream.

Link comparisons with `paired_probe_id` and list `deliberate_differences`. All other world facts, controller settings and hypotheses remain identical. Assign every bound variable in every case. `world_setup` is authored ground truth; `controller` is a requested target; `subject_behavior.value` remains null until recording. Do not infer realized behavior from a setpoint.

## Recording and budget

Each case has `recording_description`: channels with names, units, rates, methods, windows, reference frames and uncertainties; authored context inputs with names, units and methods; and limitations. Include the judgment entry's required observations and context. Never promise arbitrary future predicates or proof of intent.

Default selection uses three attempts per sweep: endpoints then midpoint, followed by recursive bisection for larger budgets. Joint grids use corners, center, then deterministic component ranks. The complete grid remains unchanged; unrun points are unselected. Explicit case selection overrides this default. Failed attempts consume budget and are preserved. Routine capture/controller repairs execute the same frozen setting after an evidence-backed construction change; they do not select new points or retry unchanged code for a favorable label. Retain failed attempts internally and keep approved range, spacing, and target values unchanged.

Before dispatch, record selected law/cell/actor/case identities and explicit training/testing/heldout splits in `sets/<set-id>/selection.json`. Freeze membership; an extension needs a new selection version. Record dispositions as execution progresses. Report completion against the reviewed cell requirements and frozen selection. Account for unselected definitions separately from required pending work and exhaustive law coverage.

## Build and review

Return a draft stage artifact; see `docs/batch_pipeline.md` for the exact worker contract. Validate law/actor coverage, numeric triples, non-judgment pairs, complete or explicitly incomplete judgment sweeps, fixed comparisons, assignments, recording requirements, and absence of judgment interpretations or labels. Optional review never blocks execution.

Preserve consumed versions and review provenance. All persistent outputs belong beneath `pipeline_paths.py`'s root. Do not consume historical declaration-based cases or regenerate reviewed examples.

## Expected scenario labels and complete applicability

Before accepting a deterministic case, resolve the target rule’s activation, applicable branch, exceptions, boundaries and required recorded actions. Include fixed synthetic assumptions and their provenance in the case definition and adapter context evidence; unknown required context means repair is needed, not a completed unlabeled case. Use expected_label for the outcome supported by the full delivered trace wherever the target rule applies: compliant, non_compliant, or not_applicable. Keep the intended outcome and physical execution status separate. Actual judgment sweeps explicitly omit expected labels. Do not call these labels legal labels or formalization verdicts.

For signal-distance probes, declare business/residential versus other-area context and verify continuous signal activation and actual course-change onset; a command-to-planned-station distance is not the observed distance. For stop probes, resolve the crosswalk/stop-line hierarchy and verify stationary behavior before the applicable boundary. For lane-count probes, count same-direction clearly marked lanes; one lane is not_applicable, while active cases need explicit fixed signaling and safety assumptions. Direction arrows and centerlines in review videos must come from recorded native geometry and delivered lane direction data. Posted-speed videos must identify the governed portion’s boundary and check that unrelated signal-controlled regions do not interfere. Preserve approved targets and original evidence when repairing constructions.

For speed probes, use the shared `batch_pipeline/speed_policy.py`: SI m/s internally, explicit mph/km/h reporting, default below/above margins of ±5 mph, and a middle command 0.5 mph inside the compliant side. Record an override reason when a different margin is appropriate, such as at low speeds. The middle is a near-boundary case, not an exact-equality test. Measured samples, not commands, determine expected outcomes over all applicable delivered evidence. Flag an overshoot and repair its cause under existing authorization; never clamp observed speed.

Primary review videos cover exactly the delivered trace; focused previews are optional and supplementary. Store each accepted full video/Lean JSON pair once in `recordings/RECORDING_ID`. Finalize the frozen law set once using `pipeline.py finalize-set --set SET_ID`; portable packaging is an explicit optional operation. Deterministic missing evidence or an unintended outcome triggers diagnosis, actual repair, rerun, and validation while independent work continues. Only necessary changes outside the approved scenario/targets require a user decision.

See [the storage workflow](../../docs/storage.md) for selection schema and finalization. Acceptance updates the canonical recording and run-local index; it does not finalize the set. Leave finalization deferred until the complete selected set has terminal dispositions.

Use `sets/index.json` to identify active `demo-train`, `demo-test`, `held-out`, `full-train`, and `full-test` sets. Read each set's `scope.json` for precomputed cell ownership and reviewed assignments, and `selection.json` for recording membership. Full sets include their demo subset through shared recording IDs. Preserve capture-time provenance. Active membership may change only through a registered law-split migration receipt; unexplained repartition or actor substitution remains invalid. `organize-sets` is a metadata-only migration, not a per-case step. See [the active split sets](../../docs/storage.md#active-split-sets).

Use [the workspace index](../../docs/storage.md#active-implementation-workspaces) for active implementation: `work/{demo,held-out,train,test}/<cell>/<law>/`. Full sets share their demo workspace. Use `workspaces` path helpers for campaign administration and shared semantic outputs. Historical campaign directories are recovery sources; new edits belong in indexed workspaces and require fresh frozen runtime provenance before execution.

For the active `demo-overlap-v3` split, resolve law partition and scenario eligibility through `law_split` and current set scopes. Cells are shared by law-specific assignments. Preserve the demo and historical source data; do not infer partition from a campaign name or the old global cell lists. See [versioned law partitions](../../docs/storage.md#versioned-law-partitions).

## Authored intention contract

Keep scene facts, scenario assumptions, and vehicle intentions separate. Read [the shared intention contract](../../docs/intention_contract.md) when a case contains intention. The selected Core `Intentions.lean` owns its meaning; IDs come from the authored plan, not a fixed skill vocabulary. Require a recorded vehicle/target binding, source, explicit values and temporal scope. Omitted declarations remain unknown; do not infer intentions from signals, outcomes or case names, or put road geometry and legal premises inside `intents`. Visibility in video does not decide whether a fact belongs in the scene. Missing bindings are unsupported input, never invented targets. Keep the existing world_setup/controller/subject_behavior variable classification.
