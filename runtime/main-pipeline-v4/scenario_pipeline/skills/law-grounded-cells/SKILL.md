---
name: law-grounded-cells
description: Extract law-cited layouts, intended maneuvers, activation controls, and obligated parties from a traffic-law corpus, then build or extend a domain-filtered catalog of candidate driving-problem cells. Use for this scenario_pipeline repository's law-grounded vocabulary and cell creation, not simulator scenario generation.
---

# Law-grounded driving cells

Work from the `scenario_pipeline` repository containing this skill. Its `catalog.py`, `data/terms.json`, and `data/law_annotations.jsonl` define the current schema and reviewed vocabulary; read the relevant parts before changing them. Require a law-corpus path from the request or existing task context; if it is missing, ask rather than guessing. Use the requested output directory, or the central `../runs/scenario_pipeline/work/<category>/_campaigns/<run-id>` directory when none is specified. Load an existing `vocabulary_catalog.json` there and extend it through the builder; preserve supported vocabulary and stable IDs.

## Extract from law text

Process large corpora in reviewable batches. For each law, record exact-text evidence and distinguish:

- **Layout:** road topology, geometry, lane structure, or district context. It exists independently of the participants and controls. A law with broad road scope need not invent an `unspecified` layout value.
- **Maneuver:** the ego's intended task, including prohibited goals when a law addresses them. Braking, yielding, and other compelled responses are conditions or behavior, not new intended goals. `travel`, `follow`, and `reverse` are domain-neutral maneuvers, tagged `general` in this catalog.
- **Control:** the particular participant, object, marking, sign, curb color, or designated space that activates the law. Physical permanence does not make an activation object a layout. Use `other_vehicle` for ordinary vehicle participants; put leading, oncoming, circulating, stopped, and similar roles or states in `participant_conditions`.

Reuse canonical IDs and record synonyms rather than duplicating terms. Every term needs a specific source-law citation and exact supporting quote. Assign `obligated_parties` to each evidence quote and joint fact pattern, and `term_parties` to each layout, maneuver, and control cited by that law. Review which actor each clause directs; the older law-level `ego_subject` is context, not a source of cell actors. Separate joint fact patterns from terms merely mentioned in the same law: only a reviewed joint pattern grounds a cell. A law that mentions all three items without jointly asserting them can support a `law_cooccurrence` exception, but not `grounded` status. Preserve the full law text and its conditions.

## Form candidates

Use the repository builder to enumerate the structural product of real layout, maneuver, and control values; exclude placeholders. Retain every grounded triple. For a plausible ungrounded triple, `general` acts as a wildcard **only for the item carrying it**. The other items with specific domains must share a domain; fewer than two specific-domain items have no domain conflict. Also retain a triple whose three terms occur in one law annotation, citing that law. Record the applicable `formation_basis`.

Keep all grounded cells, including those directed only at non-driver actors; `grounding_by_party` groups their supporting law IDs by the fact pattern's obligated party. Keep plausible cells for non-driver actors too. The builder derives their `candidate_ego_parties` from the maneuver's and control's cited party support, never from the layout's source actor. Generic `motor_vehicle_driver` support matches specialized bus, taxi, emergency, and heavy-vehicle drivers. `actor_status` is `compatible` when the two terms support a common party, `actor_mismatch` when their known parties conflict, and `unresolved` when support is unspecified and no compatible party is known. Retain mismatched and unresolved cells in the full catalog; they have no inferred ego party. Do not treat actor compatibility as law grounding, legal relevance, permission, or simulator feasibility.

Tag terms by what the term itself can describe, not by every setting where a law happened to mention it. Check broad or suspicious tags against the cited laws before changing them. In particular, `road_geometry` is too coarse to prove that a control about curbs, marked lanes, parking restrictions, barriers, road edges, or turnout signs belongs with every curve, crest, or winding road. Check the specific layout–control and maneuver–control evidence instead of inferring a connection from the shared tag. Existing narrow-road parking devices, grade/curb, and turnout/sign laws support those particular contexts, not a universal hazard-geometry pairing.

Do not use a simulator, create simulator artifacts, or assign structural infeasibility from absent law evidence. The optional physical-constraints mechanism is outside this law-only workflow unless the user separately requests it.

## Build and review

For new or changed laws, use `catalog.py prepare` to identify review batches, update the canonical term registry and reviewed annotations, then run `catalog.py build --corpus <explicit path> --output-dir <explicit directory>`. Run `catalog.py validate` on the output and the repository tests. Review `summary.json` (including `actor_counts`) and `domain_filter_audit.json`, especially party breakdowns, mismatches, high-impact `general` tags, and same-law exceptions. Per-party counts can overlap; use `grounded_by_party_set` for exact grounded party sets. Spot-check newly grounded cells and suspicious plausible cells against source text, including their full activation conditions. Report counts, citations, and unresolved actor or tag ambiguity without silently inventing categories to make the product smaller.

## Autonomous execution and provenance

For programmatic batches, use `pipeline.py` and `docs/batch_pipeline.md`. SQLite owns job state and shared-library writes; optional campaign reports are snapshots, not a processing dependency. Semantic workers return one proposal under their stage contract and must not independently rewrite the shared library.

Human review is optional metadata, never an execution gate. Consume valid draft inputs provisionally and record exact input versions, review-status snapshots, and dependency references. Preserve an artifact's own review status separately from its sources; do not mark unreviewed evidence approved. In step 1, retain contributing annotation identities and review status on vocabulary and cells; in step 2, record the catalog facts, annotation provenance, summaries and full texts actually consumed. Later stages retain references without redoing upstream semantic checks merely to propagate labels. Judgment meanings remain unknown throughout this pipeline. Shared law-judgment-observables requirements drive fixed physical sweeps and recording; no skill may propose or consume a judgment value or label a judgment-law case. Record the consumed requirements and frozen sweep versions. Later legal interpretation and labeling are outside this pipeline. Invalid evidence, missing inputs and unsupported scope block affected work; lack of approval does not.

All persistent outputs use the root declared by `pipeline_paths.py` (default `../runs/scenario_pipeline`). Do not create generated reports, traces, graphs, videos or Lean modules inside source or third-party trees.

Follow [the storage workflow](../../docs/storage.md): frozen inputs belong in `inputs/`, mutable semantic outputs in cell `_shared/semantic/` directories and campaign administration in `<category>/_campaigns/`, and SQLite state in `state/`. Do not create per-cell exports, merge historical delivery trees, or package recordings during semantic stages.

Use [the workspace index](../../docs/storage.md#active-implementation-workspaces) for active implementation: `work/{demo,held-out,train,test}/<cell>/<law>/`. Full sets share their demo workspace. Use `workspaces` path helpers for campaign administration and shared semantic outputs. Historical campaign directories are recovery sources; new edits belong in indexed workspaces and require fresh frozen runtime provenance before execution.
