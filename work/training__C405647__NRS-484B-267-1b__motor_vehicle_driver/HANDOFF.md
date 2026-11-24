# training__C405647__NRS-484B-267-1b__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Current CPU rebind (2026-11-23)

The canonical assignment is now bound to SHA-256 `0ee3f348d7db64723f6be4dab6257853965bc6626f68567df96d31ee3b5d01cd` through its numbered `law` object. The authored Native request and capture window now spans 600 frames at 20 Hz (30 seconds), including four original-camera channels. The current unselected construction manifest is `f88b35930aa70ea001c8e4c9cfa5b4be45e3aa05aeadcff3ac399c79d5b4db05`. All eight primary/fallback bundles passed pinned offline preflight with no simulation (`draft-offline-audit.json` SHA-256 `822bcab31a3472dca5c31ebf72bcfc731483fa77805968b167c9f6b8b7beebbb`).

The current measurement contract uses `worker-measurement-contract`. Eight exact 600-frame synthetic finalizer positives and altered-join and missing-source negatives passed (`exact-finalization-proof.json` SHA-256 `a87a415d00fdd95abafe593fde4ea6b57f7b55a61368356b116268e67ebdb3e5`; independent selected-measurement audit SHA-256 `1b96e0aa09a89db9de38a48e60684cdd914380a8dff6890b6ccb45143ff5e19a`). Four controlled comparison pairs and 16 nonposition-source mutations passed independent audit SHA-256 `5867e7f80fec5fb222ef4a4dde4240b151d28451f31e65c73f50daf7db0938ff`. Eight exact saved-package positives and removed-source negatives passed audit SHA-256 `012f8ae060fcf20c3dc300d72f6f48161920f18c16cc1e42ac0c1e8284bd38f7`. Statutory review recomputed 4,800 saved rows and 11 topic joins; audit SHA-256 `b8febda1793ef9f0ffb4c22bb9351d7e6e456c78810424f77b6cb9fc2aaa7510`. Assignment-scoped `worker_check.py --complete` passed.

These are unselected CPU diagnostics. The old `full-package-*` receipts still describe a 480-frame legacy fixture and are historical; do not use them for current runtime compatibility. Next construct a source-hashed current fixture recipe with all four cameras, run `runtime.py compatibility` for each exact candidate with the 600-frame finalizer and strict measurement contract, then exercise `process-saved` and independent delivery/comparison audits. Keep original Native authority, lamp pixels, shoulder-sign qualification and legal judgment open until source review. No readiness or accepted recording is claimed.

## New unselected CPU construction

`native/build.py` now emits an authored 260 m OpenDRIVE road with two eastbound
driving lanes and a distinct shoulder, plus 600-frame, 20 Hz paired right-edge
requests for both controlled cases. It emits primary and three distinct fallback
requests per case and reflects OpenDRIVE y into proposed Native coordinates.
The reference requests a stop at x=48 m, y=-6.0 m, parallel to the edge and
with its authored 1.8 m body entirely inside the driving lane. The contrast
requests the same longitudinal stop in the inner lane. Their approach actor,
lamp request, officer-direction request, shoulder-sign context and frame plan
are identical within each candidate pair.

`native/audit.py` independently checks the exact source and plan hashes, lane
geometry, frame joins, y reflection, controlled pair, measured motion and
six deliberately corrupted packets. The primary reference first moves
laterally at frame 6, reaches the authored edge target at frame 62 and stops
at frame 120; the approach reaches its authored catch-up threshold at frame
159. Fallback 1 starts movement at frame 2, fallback 2 reaches the target at
frame 43, and fallback 3 increases the authored front-lamp frustum estimate
from 23 to 33 frames before catch-up. These are CPU request measurements, not
observed CARLA trajectories, original camera pixels, qualifying lamps,
vehicle authority, a finding that the response was legally immediate, or a
legal judgment of “as close as possible.”

## Native and saved processing

`native/runner.py` now has a CPU preflight and an unexecuted original CARLA
capture path. It requires an idle exclusive server, imports the exact authored
OpenDRIVE, checks starting lanes and four-wheel control geometry, records
observed actor centers, four-vertex body footprints, headings and speeds, and
captures four synchronized original RGB cameras as FFV1 at 20 Hz. The capture
report retains restoration/error state and explicitly sets accepted=false.
`native/prove_runner.py` passes all eight exact candidate preflights and three
wrong-identity/hash negatives without importing CARLA.

`native/prepare_original.py` is the saved-only bridge for a future original
capture. It requires a sealed 600-frame capture and map readback, exact bundle
identity, all four camera source hashes, decoded FFV1 dimensions and frame
counts, and actor/video frame joins before reflecting Native coordinates into
authored OpenDRIVE coordinates. `native/prove_original_bridge.py` passes three
missing/inconsistent original-source negatives. It has no original-capture
positive yet.
`native/measure_saved.py` computes saved motion, body-edge, heading, stop and
catch-up diagnostics without a legal verdict. `native/prove_saved.py` passes
eight synthetic 600-frame positives and six corrupted-source negatives;
`native/audit_saved.py` independently recomputes the paired edge/catch-up
contrast. `native/measurement-contract.json` names the required original
channels and the unresolved source/legal observations. Synthetic CPU packets
are not original video or accepted delivery evidence.

`build_offline.py` materializes the exact Native sources, authored map, both
600-frame request tracks, the frozen assignment source, candidate config and
three CPU tests into each of
eight unselected bundles. All eight pinned `runtime.py offline` commands pass;
`audit-draft-offline.py` independently checks source equality, construction
hashes, measured fallback triggers, log hashes and three tests per bundle.
The bundle now includes `native/finalize.py`. Eight exact synthetic saved
finalizations emit analysis, a native-result shape and three recording channels;
eight altered actor/trace/video frame joins reject. `prove-finalization.py`
retains the results and `audit-finalization.py` independently checks the
receipts. Eight exact saved-processor positives and removed-source negatives
also pass with an independent audit. The synthetic full Core/Lean/render/final
decode compatibility path now passes for both cases and all four exact
candidates with a matching deleted-source negative each.
`full-package-summary.json` and `full-package-audit.json` retain the unselected
v1 receipts and independent audit. Strict v2 selected-measurement compatibility,
original Native evidence and physical delivery acceptance remain unproved.

## Source review

Law: NRS 484B.267(1)(b); with NRS 484B.210(4). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

emergency approach with fixed signal context; edge/shoulder exceptions separately. Compare only `right_edge_clear_intersection_position` (bool) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Blocker and resumption

Original CARLA capture and strict v2 selected-measurement compatibility proofs are still absent; exact statutory exceptions and historical equivalence remain unverified. Continue with original-source bridge positive proof, strict measurement contract/recipe compatibility, independent delivery and comparison audits. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.
