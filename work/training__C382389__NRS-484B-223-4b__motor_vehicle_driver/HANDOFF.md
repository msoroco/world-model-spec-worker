# C382389 · NRS 484B.223(4)(b)

Status: `blocked`. Both cases and all eight candidate bundles are unselected drafts. No physical recording or legal verdict is claimed.

The exact clause forbids travel through an intersection while driven in a single right-only turn lane. The authored same-cell map compares a straight route from adjacent lane `-1` with a straight route from proposed right-only lane `-2`. The original-frame measurement uses complete body overlap, unchanged road/lane IDs, and complete straight exit. Native right-only designation and connector identity remain unverified.

`native/` contains map, observed-pose runner, controller, four camera policies, source-bound measurement and saved finalizer. The primary and three distinct fallbacks per case have measured failure triggers; eight pinned `runtime.py offline` checks and independent source/controlled-input audits pass. Five semantic stage drafts validate with the in-memory `law_record` alias; their compliant/violating labels are proposed targets, not observed outcomes.

The 480-frame synthetic saved fixtures pass positive processing, four video-source decodes, measurement-contract verification, Native attempt validation with `rebuild_required: true`, and missing-Native-source rejection. The independent pair audit holds straight movement, geometry, x/time/frame/road trace, rate and cameras fixed; measured right-only intersection sample fractions are 0 and 1. These proofs do not establish Native physical feasibility, right-only lane designation, exact pinned-runtime compatibility, Core/render integration, or independent delivery acceptance.

Next: survey Native lane and connector identities, finish exact positive/negative compatibility receipts for each candidate, physical-preparation and Core/render saved integration, and independent delivery audits. Keep status blocked until all CPU proofs pass. The ordered GPU queue has no dispatchable row.

## Canonical original frame identity continuation

The proposed Native runner now writes `video_frame`, `native_frame`, canonical `carla_frame` and `time_s` together for every source camera frame. An independent CPU audit checks this row against the pinned frame-map writer and rejects invalid identities. All eight exact unselected primary/fallback bundles were rebuilt and passed pinned offline checks and source/controlled-input audits after this source change. No CARLA run, Core/render compatibility receipt or delivery acceptance is inferred; this assignment remains blocked.

## Exact package synthetic diagnostic continuation

The authored curved connector lane `-2` initially failed the pinned OpenDRIVE polygon parser; the work-owned 3.3 m connector repair parses into 31 road regions. All eight rebuilt bundles pass pinned offline and independent construction audits. Both 480-frame synthetic saved cases pass their positive, missing-source negative, pair comparison, Core/decoder/render and final decode checks. Eight full-resolution, exact pinned v1 package positives and matching missing-`native_samples.jsonl` negatives pass; `audit-package-probes.py` independently verifies receipt, source, current construction/runtime hashes and the absence of acceptance claims. This remains an unselected, blocked assignment. Strict v2, physical Native evidence and independent delivery acceptance are still worker-owned. See the latest RETURN-REPORT section for log hashes.
