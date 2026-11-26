# C228096 pedestrian curb-entry handoff

Status: partial. Original physical or legal completion is not claimed.

## Current CPU continuation

`sweep_construction.py` authors six bounded controller stations: departure holds at 4, 6 and 8 seconds, and vehicle starting distances of 10, 20 and 30 meters. The station implementation preserves the reviewed curb/path source gate, checks geometry and invokes pedestrian and vehicle construction through a fake Native adapter. The pinned `runtime.py expand` has been applied to `proposals/cases.json`: one baseline and 11 exact selected cases, with eight comparisons. The canonical semantic stage validator passes. `build_bundles.py` materializes all 11 source-gated diagnostic constructions and root config. `case-plan.json` now has the exact four-view camera plan. These values are sampling requests, not original realized measurements or legal cutoffs.

Next CPU actions are current-hash offline, compatibility, saved-only and independent audit proofs for every selected exact case, followed by manifest and queue-proposal regeneration. The source-observation mapping is empty because frozen source_observation_terms is empty. Run the scoped strict gate only after these artifacts agree; it currently fails while `result.json` is partial. Keep original physical feasibility, actual arrival distance, suddenness, yield opportunity and cited exceptions for later independent source review.

## Exact selected scope

Eleven case IDs share the prefix `testing__C228096__NRS-484B-283-1b__pedestrian__`: the original `close_walk_into_path`, `close_run_into_path`, `far_walk_into_path`, `close_walk_road_only`, `close_walk_remain_curb`, plus `sudden_departure-0000` through `-0002` and `yield_impossibility-0000` through `-0002`. Eight comparison IDs include `walk_vs_run`, `close_vs_far`, `path_vs_road`, `path_vs_curb`, two `sweep_sudden_departure_*` and two `sweep_yield_impossibility_*`. `case-plan.json` and `proposals/cases.json` bind the exact law, cell, case variables and fixed conditions. The introductory NRS 484B.287/.290/.350 exceptions remain unresolved.

## Constructed and tested

`curb_entry.py`, `reviewed_scene.py`, `native_adapter.py`, `runner.py`, `analysis.py`, `process_recorded_only.py`, `delivery_audit.py` and `comparison_audit.py` provide source-gated original curb/path geometry, timed pedestrian and driver vehicle motion, 900 synchronized frames, four Native cameras, saved-only finalization and independent source/video/comparison checks. `construction.json` and ten `cases/*/construction.json` bundles bind these sources. The prior five-case receipts were valid for the preceding source hash; all 11 need fresh current-hash proofs after the sampling construction and measured-channel changes.

`proposals/semantic-index.json` SHA-binds exact law/cell relevance, template, two judgment observable proposals, bindings and 11 selected cases. Canonical stage validation passes. The existing `execution-manifest.json`, `proof-summary.json` and `selected-validator-report.json` still describe the previous five-case source hash and must be regenerated. Twelve package unit tests pass, including independent eight-comparison fixed-condition and rejection checks.

`gpu-queue-proposal.json` still gives the previous five case rows and four comparison commands. It must be regenerated for all 11 cases and eight comparisons and must not be dispatched before the strict gate passes.

## Original source limits and gate

Frozen evidence has no accepted original recording, and frozen judgment range inventory has no exact C228096/pedestrian range. The original reviewed curb/path site, OpenDRIVE, actor and driver packet are absent; source-shaped diagnostic values do not establish legal or physical boundaries. Both canonical sweep plans are now expanded as engineering sampling requests. The exact `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__NRS-484B-283-1b__pedestrian --complete --require-delivery-ready` still exits 1 while the current 11-case CPU proof set is incomplete and `result.json` truthfully stays partial.

The six authored controller stations above provide the next CPU construction work. After exact-case proofs pass, local execution must provide reviewed original source packets, released Native attempts and independent physical and legal review. No queue release is proposed yet.
