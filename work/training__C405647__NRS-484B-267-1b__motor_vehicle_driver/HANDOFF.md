# training__C405647__NRS-484B-267-1b__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## New unselected CPU construction

`native/build.py` now emits an authored 260 m OpenDRIVE road with two eastbound
driving lanes and a distinct shoulder, plus 480-frame, 20 Hz paired right-edge
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
capture. It requires a sealed 480-frame capture and map readback, exact bundle
identity, all four camera source hashes, decoded FFV1 dimensions and frame
counts, and actor/video frame joins before reflecting Native coordinates into
authored OpenDRIVE coordinates. `native/prove_original_bridge.py` passes three
missing/inconsistent original-source negatives. It has no original-capture
positive yet.
`native/measure_saved.py` computes saved motion, body-edge, heading, stop and
catch-up diagnostics without a legal verdict. `native/prove_saved.py` passes
eight synthetic 480-frame positives and six corrupted-source negatives;
`native/audit_saved.py` independently recomputes the paired edge/catch-up
contrast. `native/measurement-contract.json` names the required original
channels and the unresolved source/legal observations. Synthetic CPU packets
are not original video or accepted delivery evidence.

`build_offline.py` materializes the exact Native sources, authored map, both
480-frame request tracks, the frozen assignment source, candidate config and
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
