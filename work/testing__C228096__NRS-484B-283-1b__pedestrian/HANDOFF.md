# C228096 pedestrian curb-entry handoff

Status: partial, source gated. Original physical or legal completion is not claimed.

## Exact selected scope

Five case IDs share the prefix `testing__C228096__NRS-484B-283-1b__pedestrian__`: `close_walk_into_path`, `close_run_into_path`, `far_walk_into_path`, `close_walk_road_only`, `close_walk_remain_curb`. Four controlled comparison IDs are `walk_vs_run`, `close_vs_far`, `path_vs_road`, `path_vs_curb`. `case-plan.json` and `proposals/cases.json` bind the exact law, cell, case variables and fixed conditions. The introductory NRS 484B.287/.290/.350 exceptions remain unresolved.

## Constructed and tested

`curb_entry.py`, `reviewed_scene.py`, `native_adapter.py`, `runner.py`, `analysis.py`, `process_recorded_only.py`, `delivery_audit.py` and `comparison_audit.py` provide source-gated original curb/path geometry, timed pedestrian and driver vehicle motion, 900 synchronized frames, four Native cameras, saved-only finalization and independent source/video/comparison checks. `construction.json` and four `cases/*/construction.json` bundles bind these sources. All five exact bundles pass pinned offline and full positive/negative compatibility checks, including Native validation, converter, Lean decoder, render and four cameras. All five pass pinned recorded-only saved processing with acquisition bytes preserved.

`proposals/semantic-index.json` SHA-binds exact law/cell relevance, template, two judgment observable proposals, bindings and selected cases. Canonical stage validation passes. `execution-manifest.json` binds all five source-gated selected delivery intents to current offline, compatibility, saved, three-outcome synthetic physical, lifecycle and positive/negative delivery audit receipts. Independent comparison audit tests pass. Nine unit tests pass. `proof-summary.json` lists every exact case receipt and SHA-256; `selected-validator-report.json` records direct validator results. Semantic, package compatibility, physical preparation and delivery acceptance validators pass. The in-memory downstream selected structure probe passes, but it is not a sweep expansion.

`gpu-queue-proposal.json` gives five exact case rows and four comparison commands for local integration. It is marked source gated and must not be dispatched before the strict gate passes. All returned files are UTF-8, below 2 MiB, and have clean EOF/whitespace; generated caches were removed.

## Exact external dependency and gate

Frozen evidence has no accepted original recording, and frozen judgment range inventory has no exact C228096/pedestrian range. The original reviewed curb/path site, OpenDRIVE, actor and driver packet, and source-supported physically feasible control ranges/spacing are missing for `suddenly leave a curb or other place of safety` and `so close that it is impossible for the driver to yield`. Both canonical sweep plans are explicitly incomplete. Source-shaped diagnostic values do not establish legal or physical boundaries. The selected execution validator fails exactly `Expand sweeps with the main implementation before manifest generation`. The exact `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__NRS-484B-283-1b__pedestrian --complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain`, because `result.json` truthfully stays partial.

When reviewed sources arrive, construct physically feasible below/interior/above judgment sweeps, add exact selected cases and current-hash proofs, capture released original Native attempts, and run independent delivery, physical and legal review. No queue release is proposed yet.
