---
name: law-cell-bindings
description: Build or extend a shared actor-specific law-template library and per-cell bindings that classify relevant laws as direct, general_duty, or requires_context, with deduplicated fixed and variable parameters. Use for scenario_pipeline step 3 after law-relevance-mapping has produced a reviewed relevant-laws draft, not for selecting laws from raw text.
---

# Law templates and cell bindings

Work from the `scenario_pipeline` repository containing this skill. Read the requested cell in the catalog, its available `law-relevance-mapping` draft, and the matching pre-extracted law structures before building bindings. Use paths supplied by the request or existing task context; ask if a required input is missing rather than guessing. The relevance draft determines **which** law–actor pairs to process, including low-confidence pairs. Do not add, omit, or reselect laws in this step. Use full law text to verify exact evidence and resolve extraction conflicts, not as a substitute for the relevance draft. If a selected law has no pre-extracted structure, stop and flag it for review.

## Build shared law templates

Store each actor-specific law breakdown **once** in the shared library under a stable `law_id@actor` key. Every cell needing that breakdown references the same template; never copy its structure into a cell record. Preserve activation, obligation, exceptions and their source clauses, timing, required observations, and unresolved `residue`. Keep actor variants separate even when parallel laws describe the same event. A template correction creates a preserved version; optional review is recorded without gating use.

Parse activation as the circumstances under which the duty governs, and obligation as what the actor must or must not do. A prohibited act or outcome must not be a prerequisite in its own activation condition: for example, a left-of-center prohibition on a blind curve activates from the curve and obstructed view, while left-of-center travel is the forbidden behavior. Check every template for this pattern, including turn prohibitions. Preserve actual exceptions and timing separately. This step identifies duties and judgment calls; it never decides compliance or violation.

Keep a law's stated numeric threshold in its own `numeric_conditions`, referencing a canonical measured variable and the law's operator, value, and unit. A dynamic value such as a posted limit references its shared world-setup parameter. Do not mint a top-level `speed_vs_this_law` variable or duplicate a quantity another law measures. Qualitative standards such as “reasonable speed” or “safe distance” belong **only** in `judgment_calls_needed`, with the phrase, source residue, and observations needed to evaluate it. Do not put a numeric placeholder there, including `null`, or declare its threshold in this skill; law-judgment-observables adds value-free sampling and recording requirements to that entry; its legal meaning stays unresolved.

## Bind each law to the cell

For every input law–actor pair, derive `binding_kind` from the parsed activation and the cell's established facts: `direct` when the cell itself anchors the law without another independent scene context; `general_duty` when no additional activation context is needed for that actor; or `requires_context` when an additional fact is needed. `direct` does not assert that a value-level test has already passed. Preserve step 2's `relevance_type` as its separate textual-relevance judgment. **Never copy `relevance_type` into `binding_kind`:** a law labeled `general_duty` upstream can require an unstated device, jurisdiction, participant, or other context here. This is a new classification, not a re-audit of step 2's law selection.

Represent each missing context as a named reusable guard, such as `school_zone`, `business_district`, or `no_u_turn_device`. Keep every `requires_context` match in `context_refs`, with its missing guard alternatives and template reference. It contributes no variables to the base cell. Move it into the resolved `law_refs` and include its parameters only when the guard is explicitly attached or unambiguously established by the cell's stated facts. A generic turn-prohibition device does not establish a U-turn prohibition; an unspecified jurisdiction does not establish a city ordinance. Do not call a law `general_duty` merely because its missing context is common.

## Canonicalize parameters

Give each distinct quantity one canonical name across laws; use a derived field of a shared parameter when appropriate. Keep fixed parameters to facts the cell actually states, including its layout, intended maneuver, control, and actor variant. Build variable parameters from the union of active templates' references, deduplicated by canonical name and linked back to the using laws. Guarded templates add no base variables.

Classify every variable using the reviewed three-way registry: `world_setup` is authored scene ground truth before movement; `subject_behavior` is an actual ego or other participant outcome confirmed only from a trace; `controller` is a target requested of a lower-level controller, not an observed result. Use one shared controller parameter per action across laws. Never assign a subject-behavior value as guaranteed because a controller target requests it. Keep judgment standards out of the variable registry. Include the active law observable requirements using canonical physical parameters; never add conditional-law observations to base variables.

Carry the required observations from every active actor-specific law into downstream recording requirements, including statutory numeric laws, general duties, and judgment-call laws. Retain the originating law/template references and canonical observation names so construction can derive capture requirements automatically. A law without a judgment sweep still needs its activation, obligation, exception, and timing evidence recorded. Unattached context laws contribute no recording requirements.

## Build and review

Historical C353238 shapes remain read-only references under `inputs/bundles/historical-context/C353238`; obsolete pilot builders are frozen under `inputs/retired-pilot`, not supported entrypoints. `data/variable_type_registry.json` defines the reviewed three-way classification. Validate the current catalog, JSON shape, exact quotes, template keys, complete law–actor coverage, guard resolution, parameter references and types, and repository tests. A step-2 `general_duty` law whose activation needs an unstated fact must remain `requires_context`.

Write draft templates and cell bindings in the requested output directory, or the central `../runs/scenario_pipeline/work/<category>/_campaigns/<run-id>` directory when none is specified. Record optional human review separately; unreviewed outputs may proceed provisionally after automated checks. Report unresolved extraction or context ambiguity; do not silently fill it with a guessed fact or number.

