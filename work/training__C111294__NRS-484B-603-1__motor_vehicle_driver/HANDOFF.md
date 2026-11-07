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

The measurement path now normalizes either observed y travel direction, including the reflected Native coordinate orientation of this OpenDRIVE proposal. A third reflected decreasing-speed positive and a pose/velocity disagreement negative pass. The independent audit checks all three positive source hashes and speed differences. This is a synthetic coordinate and data-integrity proof, not Native lane readback.

Still required: Native runner/camera/route construction for this law, exact offline and positive/negative pinned compatibility per candidate, saved Core/Lean/video fixtures, independent selected audit, statutory runnable closure, controlled comparison acceptance and ordered GPU queue entries. Keep `result.json` blocked and unselected until those CPU proofs pass.

The same-cell authored OpenDRIVE intersection proposal is retained in `draft-fixtures/road.xodr` (SHA-256 `bc708461e9ccb79fef6df587b5e13189197a2cc0e31c535a5edbe374fe45327e`). `prove-geometry.py` verifies its six road segments, junction links, continuous 3.5 m ego lane, and 480-frame synthetic body-center containment for both profiles. It passes. CARLA import, reflected Native lane readback and physical tracking are not observed.

## Exact Native/offline continuation

The assignment now has a proposed executable `native/runner.py` with eight CPU preflights and a dedicated `engineering.py` controller. It requests the authored road through CARLA only when the operator runs `--execute`; it surveys the reflected ego lane and cross-traffic lane, checks actor roles, records Native samples and four original camera streams, invokes the pinned capture and composer, and restores the operator world. It has **not** been executed against CARLA. The `probe_a` controller reduces its requested speed before the junction using observed Native y, while `probe_b` holds 30 mph; measured velocity and crossing windows still decide whether the attempted relation occurred. Three local CPU tests check all eight construction identities, profile/controller response, and fallback advancement from a source-hashed saved trace, including changed-source and exhausted-fallback checks.

`build-exact-drafts.py` materializes both cases with primary plus three distinct fallbacks each, the exact Native source files, OpenDRIVE and camera plan, case config and measurement contract. All eight pinned `runtime.py offline` commands pass. `audit-exact-offline.py` independently checks each materialized construction hash, test and command receipt, frozen source hash, candidate config, camera/channel identity and fallback knob differences. The manifest and summary hashes are recorded in the return report. These are unselected offline proofs; positive/negative pinned portable compatibility remains unfinished.

The adapted runner's first exact bundle preflight exposed that a materialized authored `road.xodr` must be present before Native execution, while a copied freshness guard rejected it. The guard now allows the authored road and rejects only prior capture artifacts. `PipelineCapture` writes Native map readback to `road.xodr` when an original attempt runs. All eight exact offline proofs and their independent audit were rerun after this repair.

`native/finalize.py` implements a saved-only source-bound measurement contract for both cases. The pinned `worker-measurement-contract-v1` validator and report verifier pass decreasing/held synthetic positives plus missing-Native-source and changed-hash negatives. The independent `audit-approach.py` checks exact statutory source binding and the two contract receipts. Full saved attempt processing through Core/Lean/video and an independent selected delivery audit remain unfinished. `result.json` remains blocked with zero fully proven candidates and no selected or accepted case.

## Exact v1 and saved integration continuation

The authored source is now `native/authored-road.xodr`, so a portable fixture may supply the separate Native capture `road.xodr` without shadowing the construction. `native/finalize.py` joins 480 Native, Core, evidence, video-map, body-history and capture-frame rows, decodes four camera sources, and emits pinned diagnostic measurement and result files. Both controlled synthetic attempts pass the pinned result and contract validators; removal of Native samples and mutation of a Core frame are rejected. Core/Lean conversion, review rendering and final video decode also pass both attempts. `audit-synthetic-integration.py` independently recomputes the joins, source hashes, measured relation and final video hashes. These are synthetic CPU fixtures, with no physical hazard or original CARLA pixels.

All eight exact unselected v1 constructions pass the pinned offline command and full-resolution synthetic positive portable compatibility. Each removed-Native-source negative fails as intended. `audit-exact-packages.py` independently checks every construction SHA, receipt, source-bound measurement, video decode and diagnostic result. The v1 receipts do not constitute selected v2 delivery proofs. The statutory branch remains pending review, and no selected case, dispatchable GPU row, physical observation or accepted recording is claimed. `result.json` remains blocked with candidate count zero.
