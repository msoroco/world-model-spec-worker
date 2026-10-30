---
name: law-judgment-observables
description: Identify value-free observable, context, sampling-dimension and recording requirements for judgment-call phrases in shared actor-specific law templates. Use before scenario-coverage-cases; never interpret a standard, choose a threshold or surrogate rule, or label compliance.
---

# Judgment observables

Work from the shared law-template library produced by `law-cell-bindings`. Process entries by law, actor, and exact phrase/note identity. Read the law evidence, activation, obligation, exceptions, timing, required observations, and residue. Do not read or modify cells, cases, recordings, or historical declarations. This is shared law-level work, not per-instance threshold selection.

## Identify evidence without defining the standard

Leave every judgment phrase unresolved. Record which physical observables and instance context a later designer's predicate could depend on, their units, useful temporal histories, and physical dimensions suitable for sampling. Describe observations without prescribing how they prove compliance. Interior mental states are not directly observable: retain actions and circumstances without proposing a surrogate rule that establishes intent. State evidence limitations explicitly; do not promise to support every imaginable predicate.

A factual or jurisdictional lookup, such as a district boundary or school calendar, remains a sourced `world_setup` fact. Flag extraction conflicts without silently altering the law. Preserve statutory numeric thresholds; they are not judgment values.

## Record shared requirements

Attach `observable_requirements` to the same `judgment_calls_needed` entry, using these lists:

- `observables`, `context_inputs`, `sweep_dimensions`, and `recording_needs`: entries with canonical `name`, `unit`, and value-free `description`.
- `landmarks`: reference definitions with `name`, `description`, `source`, and actual `verification_evidence`. Engineering references can supply coverage landmarks, never an adopted legal standard. Leave this list empty when no verified reference is available.
- `limitations`: missing capabilities, uncertainty, and facts recordings cannot establish.

Do not include selected numbers, bounds, operators, formulas, decision patterns, or an approved interpretation. The later case planner supplies physical ranges and spacing using documented instance capabilities and landmarks. The simulator records actual data. Legal meaning and labeling are outside this pipeline.

## Build and review

Return one draft proposal under the `judgment_observables` stage contract. SQLite's shared writer attaches it atomically; workers do not edit exported libraries themselves. Match phrase/note identity exactly, preserve original law fields and unrelated entries, and retain existing observable requirements during regeneration. Conflicting updates or missing matches must fail explicitly rather than erase metadata.

There is no old-declaration compatibility path. Historical declarations and reviewed recordings remain untouched and are not consumed by this skill. Fresh processing uses law text and summaries.

Validate named quantities, units, source evidence, actor separation, value-free content, preservation, and limitations. Optional review is informational metadata, never an execution gate or a legal interpretation. Save persistent outputs only beneath the root in `pipeline_paths.py`.

Follow [the storage workflow](../../docs/storage.md): frozen inputs belong in `inputs/`, mutable semantic outputs in cell `_shared/semantic/` directories and campaign administration in `<category>/_campaigns/`, and SQLite state in `state/`. Do not create per-cell exports, merge historical delivery trees, or package recordings during semantic stages.

Use [the workspace index](../../docs/storage.md#active-implementation-workspaces) for active implementation: `work/{demo,held-out,train,test}/<cell>/<law>/`. Full sets share their demo workspace. Use `workspaces` path helpers for campaign administration and shared semantic outputs. Historical campaign directories are recovery sources; new edits belong in indexed workspaces and require fresh frozen runtime provenance before execution.
