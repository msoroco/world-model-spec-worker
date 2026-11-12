# heldout__C230671__NRS-484B-403-1__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.403(1) — A U-turn may be made on any road where the turn can be made with safety, except as prohibited by this section [NRS-484B-403-2, NRS-484B-403-3] and by the provisions of NRS 484B.227, 484B.363 and 484B.407 [NRS-484B-227-1, NRS-484B-363-3, NRS-484B-407].
- Cell/actor: C230671 / motor_vehicle_driver; layout `road`, maneuver `u_turn`, control `other_vehicle`.
- Exact input: `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/assignment.json` (SHA256 `834dd810ea6cd5332d5adf243bf6ee56e31cd839347bcb0d2da2b553507f9086`).
- Witness: `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.u_turn, st.roadway, drv.time_to_conflict, rel.oncoming, drv.following, st.sight_distance, kin.speed, drv.hard_deceleration.

## Required source and construction review

1. All incorporated prohibition conditions.
2. Establish public vehicular use, highway boundaries and location outside city territorial limits.
3. Identify the driver in actual physical control and qualifying vehicle.
4. Other vehicle's actual route, position, speed and motion relative to the reversal.
5. Preserve the unresolved safety standard and obtain the full incorporated prohibition texts before determining their applicability.
6. Qualifying road and conventional motor vehicle with an identified driver in physical control.
7. Realizable turning envelope and observations throughout constituent movements.
8. Supply a realizable reversal path, surrounding vehicle trajectories, visibility and observations throughout all constituent movements.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C230671__NRS-484B-403-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C230671__NRS-484B-403-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## C230671 identity-rebound primary construction checkpoint

The frozen C230671 assignment has the same NRS 484B.403(1) law text, eight observation terms and empty accepted-evidence inventory as C230627, but its cell control is `other_vehicle` and its witness is index 162, “Conditional permission with surrounding vehicle interaction.” The C230627 Native construction supplies an oncoming and a following motor vehicle with original frame-aligned actor positions and speeds. C230671 copies the source implementation under its own identity; this is code reuse, not reuse of C230627 evidence or proof receipts. The plan now cites C230671's witness and keeps public vehicular use, road boundaries, city limits, qualifying driver/vehicle, safety and incorporated prohibition applicability unresolved for original-source review.

The C230671 primary `__safety_clear` inline construction is identity-bound, and its exact offline and positive/missing-original compatibility commands passed against the pinned CPU runtime. Its fallback proof sweep was interrupted after the primary because fallback construction files were temporarily staged to respect the repository's 10,200 returned-file cap. The first fallback failed solely with `FileNotFoundError` for its staged construction; it has since been restored and its construction hash rebound. That failure is not a physical or legal result. Current main manifest intentionally contains only the first selected case, with proof fields unclaimed, while all six other cases and unused source files are staged under ignored `.runtime-work/c230671-staging` for compactness. Source/proof construction is incomplete; `result.json` remains partial.

Resume by confirming global return-file margin with the batch owner, restoring the minimum staged source files, rebinding construction and diagnostic hashes, and rerunning `prove_exact_matrix.py --case-suffix safety_clear`. Then run the primary saved-only path and independent delivery audit before restoring the six other exact cases, their three fallbacks each, physical receipts, semantic drafts and strict gate. Do not infer safety or public-road status from synthetic diagnostics.

## First complete C230671 exact case

`__safety_clear` primary and its three distinct physical-risk fallback constructions passed exact offline and positive/missing-original compatibility using C230671 source-bound diagnostic recipes and constructions. Its saved-only processing preserved originals and passed analysis/converter/render/four-camera decoding. The independent delivery audit accepted the positive original and rejected the tampered motion hash. No C230627 proof receipt was copied or claimed. Current one-case execution manifest SHA-256 `b377624a05ed2ead5b774a32087e0b68cef013090cb853627447cb28406c01c6`; saved-processing log SHA-256 `7cb22489341ec7de12d7b2a546714c2f2fb3d18b8dc78b04e809fa01de49da92`; delivery-positive log SHA-256 `975825719b4f143859db1c7c9b5aef93e35c04e189155dff487257136cced4f6`. Scoped `worker_check.py --complete` passes with truthful partial status.

The six further safety/prohibition cases, their fallbacks, physical-preparation receipts, semantic proposal rebind, unit suite, comparison audits and strict gate remain worker-owned CPU work. Their copied sources are staged under ignored `.runtime-work/c230671-staging` while the batch owner reduces the global returned-file count. Resume by restoring each case's source config, construction, diagnostic recipe and contract, recomputing hashes, and proving it before moving to the next. Original Native public-road/authority, other-vehicle behavior, camera visibility and legal judgments remain local review only.

## Other-vehicle contrast primary checkpoint

The `__safety_conflict` primary changes the planned oncoming vehicle placement from 24 m to 12 m while keeping the U-turn/camera/duration contract and preserving legal safety as unknown. Its C230671 exact offline and positive/missing-original compatibility proofs pass, and saved-only processing passes. The three fallback constructions, independent delivery and safety comparison audits remain to be rebound and proved. The matrix script stopped at fallback1 solely because its construction was staged for the global file cap; its primary proof fields were bound separately. Current two-case manifest SHA-256 `d79749dc45c3b4f95bf6ac9c077820c371e99b3718be115422f3d5cc97965f79`. Scoped nonstrict complete passes with partial status. Resume the three safety_conflict fallbacks when file margin allows, then run its source audit and the safety comparison before advancing the five cited-prohibition cases.

The independent safety comparison audit now passes on C230671 sources (`safety-comparison-audit.log`): identical construction implementation/cameras/geometry and diagnostic source graph, with only the declared 8 m oncoming placement difference. It leaves physical and legal safety verdicts null. Diagnostic physical-completion/lifecycle controls for the two constructed cases also passed in ignored staging; their receipts are not yet returned or claimed in the main manifest while file-cap margin is constrained.

### Safety-pair exact fallback rebound

All four `__safety_conflict` constructions (primary plus three source-hashed physical-risk fallbacks) pass C230671 exact offline and positive/missing-original compatibility, and its saved-only processing passes. The independent safety comparison passes with only the declared oncoming-distance change. A two-case delivery audit ran successfully in ignored staging, but its conflict log and main-manifest acceptance binding remain unreturned because the global return-file count reached 10,199; no delivery receipt is claimed yet for this second case. Current two-case main manifest SHA-256 `b3e5e73e0edab417acaf889806a42743c4f5d1fc69b0ad425bc117959dcebb11`. Scoped `worker_check.py --complete` passes with truthful partial status. Next restore local audit source modules and bind the two-case delivery audit when file margin permits, then add the five cited-prohibition cases and all their proofs.

### Three-case exact checkpoint for synchronized batch gate

`__prohibition_403_2` now adds a Native mapped no-U-turn landmark candidate while retaining official device status, governing lane and pixel visibility as unknown. Its primary plus three distinct physical-risk fallback constructions pass exact offline and positive/missing-original compatibility. Saved-only processing and independent positive/tampered-original delivery audit pass, as does the fixed-condition mapped-device comparison against `__safety_clear`. The safety pair's second delivery audit is also returned and bound. No device prohibition or legal outcome is inferred from the diagnostic landmark.

The current three-case execution manifest SHA-256 is `ed85116b070004facaa765b8f9797e362ee80915b74b7dac95991de91789a2a2`. Scoped `worker_check.py --complete` passes with truthful partial status. Four selected cited-prohibition cases, physical-preparation receipts, complete semantic handoff and strict gate remain worker-owned CPU work. Resume from staged C230671 source files after the batch gate quiet window.

### Four-case exact frontage checkpoint

`__prohibition_403_3` uses original Native building-box projection within the 600 ft window and a separately sourced-use field. The diagnostic has 110 m built frontage but zero sourced qualifying-use frontage; business district legal status, intersection and divided-opening alternatives stay unresolved. Its primary plus three fallbacks pass exact offline and positive/missing-original compatibility; saved-only and independent delivery audits pass; the fixed-condition frontage comparison passes. No district prohibition is claimed. The four-case manifest SHA-256 is `c485ec44da5d1b60d7ace87a3703b7deb186cae190507c293b7b523ee539fc06`; scoped `worker_check.py --complete` passes with partial status. Next build the staged 227, 363 and 407 exact packages, then physical/semantic receipts and strict gate.
