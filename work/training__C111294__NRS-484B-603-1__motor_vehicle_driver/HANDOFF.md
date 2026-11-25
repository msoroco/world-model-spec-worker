# Current 600-frame CPU checkpoint — 2026-11-23

This assignment remains **partial and unselected**. The older 24-second/480-frame portable receipts below are historical diagnostics. `build-600-drafts.py` preserves them and writes eight separate 30-second/600-frame exact Native drafts under `duration-600-drafts/`. `draft-execution-manifest-600.json` SHA-256 is `49b1f63b909a7fc6b363594bb81cb04f75643f9a662dc41665bd8733f109656c`. Each controlled probe has a primary and three measured-risk fallback constructions, the same authored intersection and cross-traffic route, 20 Hz plan, four cameras and unchanged statutory identity.

`prove-600-source.py` ran `runtime.py offline` for all eight exact bundles; all four bundled Native tests passed each time. It measured each materialized 600-row synthetic Native approach trace from its source hash. All eight positives show the planned early-decrease versus held-speed relation. Eight changed-hash and eight missing-source negatives rejected. `draft-600-source-proof.json` SHA-256 is `46d37120b016ffd90304e26cef39241ab08ac2f7fe37022633af1b2e688dc6f1`.

`audit-600-source.py` independently checked the 600-frame/20 Hz joins, source and construction hashes, four candidate sets, fallback knob declarations, identical controlled initial state and cross-traffic trajectory, and recomputed the approach speed difference from the retained velocity rows. `draft-600-source-audit.json` SHA-256 is `afd670327aee7d3adaf5a243a09a77dc582cd8d46dabf3cd47eea4911ddd89ad`. The frozen current assignment input SHA-256 is `5144369b59ddd8c5661375847da5badffc1444db61c578fdea49cdcb852eec57`.

Next CPU work: convert the 600-frame drafts to current JSON graph and explicit fixture recipe compatibility, source-derived four-camera saved processing with Core/Lean/video, selected exact manifest, full statutory branch matrix, semantic proposals and independent delivery/comparison audits, then queue integration. The synthetic diagnostics do not prove original CARLA motion, a real hazard requiring a particular reduction, original pixels, or a legal outcome.

---

# NRS-484B-603-1 at C111294

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `other_vehicle`.

Witness branch: Approaching and crossing an intersection..

Comparison variable: `hazard_approach_speed_profile`. Proposed physical probes: decrease speed approaching a documented hazard; hold speed approaching the same hazard. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C111294__NRS-484B-603-1__motor_vehicle_driver/assignment.json`, SHA-256 `fdd355041381080ca2a7ca58c33857227647a6739b3b7310f7c6725fe97eccba`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Current gap: Eight unselected Native constructions pass exact offline and v1 diagnostic compatibility, and saved synthetic processing and independent audits pass. Selected v2 delivery proofs, statutory runnable closure and ordered queue rows remain incomplete. Physical realization and legal outcome remain unverified.

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

`audit-synthetic-comparison.py` independently checks the saved pair's identical map, actor IDs and roles, 480-frame schedule, initial state, other-vehicle trajectory and common controller settings. It reads the saved measured relations: probe A decreases 8.844 mph before the junction, while probe B decreases 0 mph. This is a controlled synthetic diagnostic only. It does not establish the hazard's physical necessity, a violation, or accepted comparison evidence.

The generic fallback advancement was replaced with six declared source-measured conditions. Probe A advances on insufficient approach-to-entry reduction, excessive crossing peak, then preentry speed above 21 mph. Probe B advances on a material approach reduction, approach start below 29 mph, then crossing peak below 29 mph. These are engineering thresholds, not statutory thresholds. The evaluator first validates the SHA-256 and full saved Native trace; four local tests include real source-hash rejection and isolated metric branches. Every exact bundle was rebuilt, passed pinned offline and full-resolution synthetic v1 positive/negative compatibility, and passed independent source/receipt audits. The v2 selected proof and statutory branch remain open.

## Current runtime diagnostic continuation (2026-11-25)

The frozen assignment hash is `5144369b59ddd8c5661375847da5badffc1444db61c578fdea49cdcb852eec57`. `case-plan.json` now maps all 13 frozen source-observation terms to recorded channels or cited law context; curvature, crest, narrow/winding road, pedestrian and weather/road alternatives remain pending, not represented by the intersection cell. The two controlled exact cases remain `training__C111294__NRS-484B-603-1__motor_vehicle_driver__probe_a` and `training__C111294__NRS-484B-603-1__motor_vehicle_driver__probe_b`.

`build-current-v2-diagnostic.py` derives source-hashed 600-frame fixtures and current-runtime copied constructions from the preserved exact primary drafts. Both cases pass `runtime.py compatibility` with four camera videos, Native samples, source-bound channel finalization, Core/Lean conversion, full video processing and a negative removing `native_samples.jsonl`. Receipts: `current-v2-probe_a-compatibility.json` and `current-v2-probe_b-compatibility.json`; corresponding positive and negative logs are retained. They are unselected synthetic CPU diagnostics. Their original CARLA hazard, pixel realism and any legal due-care judgment are unverified. `worker_check.py --assignment training__C111294__NRS-484B-603-1__motor_vehicle_driver --complete` passes while status remains partial.

Next CPU steps: complete current recorded-only saved processing with sealed Native/source receipts; bind selected construction and justified fallback candidates, semantic/physical and independent delivery/comparison audits, source-backed statutory branch disposition and exact queue entry. Run the scoped strict gate only when those proof chains are complete.
