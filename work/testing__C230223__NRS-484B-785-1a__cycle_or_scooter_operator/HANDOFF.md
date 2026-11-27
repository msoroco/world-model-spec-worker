# NRS 484B.785(1)(a) scooter bicycle lane handoff

Status: **CPU delivery prepared**. The exact assignment strict gate passed on 2026-11-26:

`.venv-cpu/bin/python worker_check.py --assignment testing__C230223__NRS-484B-785-1a__cycle_or_scooter_operator --complete --require-delivery-ready`

The source text permits an electric scooter on a roadway, bicycle lane, path or route at no more than 15 mph, subject to an ordinance enacted pursuant to NRS 484A.469. The latter source text was not supplied. This package does not claim an ordinance's legal effect or a final legal verdict. Frozen evidence has no accepted recording for this law and actor.

## Selected cases and comparisons

Six canonical cases exercise 14.5 mph, 15 mph and 15.5 mph requests; reviewed ordinance context; a device that fails the reviewed scooter definition; and the same original route outside an official bicycle lane polygon. Four controlled comparisons are `speed_below_at_above`, `ordinance_context`, `scooter_qualification` and `bicycle_lane_occupancy`. Requested controller speed is kept separate from the original measured velocity history. The baseline in `proposals/cases.json` is a semantic planning baseline and is not selected for capture.

Each case has a primary source-bound construction and a spawn-height fallback. The fallback changes only spawn Z by 8 cm and is triggered by failed primary spawn or invalid initial body-road contact. It preserves the legal comparison variables. `execution-manifest.json` binds each exact construction and offline, compatibility, saved-only, physical, independent delivery and comparison CPU proofs. `comparison-audit-specs.json` describes the review model links. `gpu-queue-proposal.json` supplies exact-case prepare, execute, saved processing, release, independent audit and accept commands, with fallback and comparison commands for lead integration.

## CPU proofs

`runtime.py verify --runtime runtime` and `runtime.py preflight` passed. All six primary and fallback offline checks, all twelve compatibility checks, six primary saved-only replays, all eighteen physical outcome fixture checks, and six Native closure lifecycle checks passed. Independent delivery protocol audits passed six positive and six negative tests. Four source-bound controlled comparison audits passed their positive and fixed-condition fault tests. These are diagnostic software checks; synthetic fixture pixels do not establish original physical visibility.

The unit command in `result.json` passed two source and configuration tests. The exact strict assignment gate passed after the final manifest and result were bound. The CPU proofs establish a portable package and reject tested invalid source bindings. They do not assert that CARLA has run this original scooter route.

## Native delivery review

The local operator must provide a reviewed official lane designation and polygon, the actual original scooter asset and manufacturer specifications, jurisdiction and enacted ordinance inventory, and CARLA endpoint details through `C230223_7851A_REVIEWED_SITE` and the canonical delivery workflow. Capture 900 original frames at 20 Hz with all four cameras, actual velocity and body corners, and the sealed original source receipt. Inspect original pixels for scooter and lane visibility, run the saved-only physical analysis and independent delivery audit, and compare original attempts using the controlled source index. Confirm the ordinance's applicability and legal effect from official text during legal review. Archive and accept only a physical and pixel-qualified recording; reject incomplete or unverified attempts.
