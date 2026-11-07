# NRS-484B-603-1 at C111294

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `other_vehicle`.

Witness branch: Approaching and crossing an intersection..

Comparison variable: `hazard_approach_speed_profile`. Proposed physical probes: decrease speed approaching a documented hazard; hold speed approaching the same hazard. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C111294__NRS-484B-603-1__motor_vehicle_driver/assignment.json`, SHA-256 `fdd355041381080ca2a7ca58c33857227647a6739b3b7310f7c6725fe97eccba`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Blocker: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

## CPU construction continuation (2026-11-06)

Added eight distinct, **unselected** primary/fallback construction targets across the two controlled speed-profile probes in `draft-candidates.json`. They keep the C111294 intersection, motor-vehicle driver, other-vehicle control, crossing bounds and 30 mph initial target fixed. Fallbacks change braking onset/target speed for the early-decrease case or other-actor approach timing for the hold-speed case. Their measured fallback triggers are in the same file. These are authoring targets and have no exact construction hashes or pinned offline/compatibility receipts yet.

`native/measure_approach.py` now validates a source-hashed 480-frame, 20 Hz Native-shaped pose/velocity trace, actor identities and roles, an intersection crossing, other-vehicle motion, continuous timing and pose/speed consistency. It measures pre-approach, pre-entry and crossing speed windows and reports `measured_early_decrease_held`, `measured_no_material_decrease` or an ambiguous diagnostic. The 3/2/1 mph thresholds are engineering surrogates, not statutory thresholds or legal verdicts. `prove-approach.py` writes the decreasing and held-speed synthetic fixtures and rejects a changed source hash and missing frame. `audit-approach.py` independently checks the frozen law text and source SHA, four unique targets per case, saved source hashes and recomputed speed differences. Both scripts pass. The other vehicle's physical hazard timing, necessity of a particular reduction, real CARLA behavior and original pixels remain unobserved.

Still required: Native runner/camera/route construction for this law, exact offline and positive/negative pinned compatibility per candidate, saved Core/Lean/video fixtures, independent selected audit, statutory runnable closure, controlled comparison acceptance and ordered GPU queue entries. Keep `result.json` blocked and unselected until those CPU proofs pass.

The same-cell authored OpenDRIVE intersection proposal is retained in `draft-fixtures/road.xodr` (SHA-256 `bc708461e9ccb79fef6df587b5e13189197a2cc0e31c535a5edbe374fe45327e`). `prove-geometry.py` verifies its six road segments, junction links, continuous 3.5 m ego lane, and 480-frame synthetic body-center containment for both profiles. It passes. CARLA import, reflected Native lane readback and physical tracking are not observed.
