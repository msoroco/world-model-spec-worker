---
name: law-relevance-mapping
description: Determine which traffic laws could apply to a scenario_pipeline catalog cell, separately for each candidate ego party, and record evidence for human review. Use for this repository's step-2 law-relevance mapping; do not re-derive grounding, domain tags, or cell formation, which belong to law-grounded-cells.
---

# Law relevance mapping

Work from the `scenario_pipeline` repository containing this skill. Read the requested cell from the catalog (normally `../runs/scenario_pipeline/inputs/catalog/vocabulary_catalog.json`), the pre-extracted law summaries at `<corpus-root>/laws/evaluation_scenario/scenarios.jsonl`, and the matching full texts at `<corpus-root>/laws/full_list/laws.jsonl`; use paths supplied by the request or existing task context, and ask if an input is missing rather than guessing. The catalog defines the cell's facts and actors, not its relevant-law list. The existing `../runs/scenario_pipeline/inputs/bundles/historical-context/C353238/documents/C353238_relevant_laws_draft.json` is a format example, not a source of relevance decisions for other cells.

## Select actor variants

For a `plausible_ungrounded` cell, evaluate each `candidate_ego_parties` value separately. For a `grounded` cell, use the parties in `grounding_by_party` as its actor variants. If neither yields a party, stop for actor review; do not invent one from layout citations, controls, or a generic driver assumption. A general driver obligation may cover a specialized vehicle driver, but a cyclist, pedestrian, and motor-vehicle driver are not interchangeable. Check each law's `subject` and actual actor scope against every variant independently, including apparently parallel statutes. Record the exact party IDs in `applies_to`; do not use a `both` shorthand, which is ambiguous for cells with more than two parties.

Ignore `grounding`, `source_laws`, `formation_basis`, and domain tags when deciding which laws are relevant. They explain how the cell was formed, not whether a law's activation conditions could hold there. Do not change those fields or re-run the `law-grounded-cells` vocabulary and cell-formation work.

## Identify potential relevance

Review the pre-extracted summaries as the primary source of relevance judgments, in batches if needed. For every summary and every actor variant, compare `subject`, `activation_conditions`, `required_observations`, exceptions, and timing with the cell's fixed layout, intended maneuver, and control. A law is potentially relevant when its conditions **could** become true without contradicting those fixed facts; this does not establish that it actually activates, is satisfied, or is violated in a trace. Retain a law that needs a compatible but unstated fact, such as a school zone, sign instruction, jurisdiction, another participant, speed, or rider subtype, at low confidence and name the missing condition in `notes`. Do not silently assume that fact is present.

Search for both `specific_match` laws, whose conditions name a cell concept, and `general_duty` laws, such as broad care, speed, or right-of-way obligations that could apply without naming any cell term. Review the summaries for general duties deliberately; a keyword match on the three cell IDs is insufficient. Compare summary IDs with the full-text corpus and search raw text for laws absent from the summary file. For a covered law, use its structured summary for the relevance judgment; use the raw text to verify an exact quote and flag a material summary/text conflict for human review rather than silently rewriting the extraction.

## Record evidence and exclusions

Write one draft JSON object with `cell_id`, `status: "draft"`, `relevant_laws`, and `borderline_excluded`. Each relevant-law entry has `law_id`, an exact supporting `quote`, `applies_to` as an array of checked party IDs, `relevance_type` (`specific_match` or `general_duty`), `confidence` (`high`, `medium`, or `low`), and `notes`. No verified quote means no inclusion. Use low confidence for a real but uncertain candidate, and state the uncertainty; do not turn unknown activation facts into a violation finding.

`borderline_excluded` is required, even if empty. For each seriously considered but rejected law, record its `law_id` and a specific `reason`, such as an incompatible subject or a required condition contradicted by the cell. Do not list every routine nonmatch. If two actor-facing entries describe the same physical object or event, flag the pairing explicitly in `notes` and check both parties independently. A suspected duplicate control belongs in a separate `law-grounded-cells` vocabulary review; do not merge terms or laws in this step.

## Build and review

Run `python3 catalog.py validate ../runs/scenario_pipeline/inputs/catalog/vocabulary_catalog.json` with Python 3.8+ to check the source catalog, then write `../runs/scenario_pipeline/work/<category>/<cell_id>/_shared/semantic/<run-id>/<actor>/relevance.json` unless the request specifies another output directory. Check its JSON shape, law IDs, actor IDs, and every quote against the supplied full text. The generic `pipeline.py` scheduler provides bounded step-2 relevance workers. Retired pilot builders are historical input references, not current entrypoints. Record optional human review separately; unreviewed outputs may proceed provisionally after automated checks.

