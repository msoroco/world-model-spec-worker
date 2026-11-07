# NRS-484B-223-3b at C394300

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `left_turn` / `center_turn_lane`.

Exact statutory source: NRS 484B.223(3)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Center-lane travel before a left turn from the highway. Planned comparison variable: `center_turn_lane_distance`. Requests: driver begins left turn within 200 feet of entering center turn lane; driver travels over 200 feet in center turn lane before left turn. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject is in a centre turn lane preparing to turn left from the highway.

Timing to retain: the distance is cumulative from entry into the lane to the start of the turn; the trace must cover both; the violation is the instant the accumulated in-lane distance passes 200 feet before the turn begins.

Exceptions and numeric alternatives planned: center turn lane travel numeric boundary 200 feet.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: Twenty unselected exact Native construction drafts, five measurement contracts, and full 480-frame synthetic saved finalization with two negatives per case now pass CPU checks and independent source/comparison audits. Strict v2 compatibility receipts, physical Native center-lane designation and route evidence, independent delivery acceptance, and selection remain absent. Exact v1 synthetic package processing passes.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 200-foot measurement prototype

The exact NRS 484B.223(3)(b) text has a 200-foot (60.96 m) upper bound on travel in a dual-direction turn-only center lane before a left turn from the highway. `native/measure_center_lane.py` now reads original Native body/pose rows and authored lane geometry, brackets first body contact and observed left-turn onset, and reports a cumulative path-distance interval. Seven adversarial CPU tests pass. On synthetic one-foot probes, 199 and 200 feet remain unresolved because the event brackets straddle the threshold; 201 feet resolves above it in that fixture. This is a sampled geometry diagnostic, not Native design or legal outcome proof. The five case drafts remain unselected; exact pinned-runtime compatibility, saved Core processing and independent delivery acceptance are still required.

## Same-cell authored geometry continuation

`native/geometry.py` now proposes an OpenDRIVE eastbound road with an adjacent through lane, center-turn lane and opposing traffic lane, plus one northbound left-turn connector. Five routes vary only the nominal lane-change station and use the same turn connector and destination. CPU checks pass XML links, route continuity, authored pavement and a prospective body proxy. The pinned runtime OpenDRIVE parser reads 17 regions, 12 lane keys and one junction note. An independent route audit confirms the shared map and five distinct commanded entry stations. The 180/220/199/200/201-foot values are controller requests; the observed body-contact-to-turn distance has not been measured on any Native recording. Dual-direction turn-only designation, connector identity and physical route tracking remain unverified. No candidate has been selected or marked ready.

## Case measurement contracts

Five unselected case-specific contracts under `draft-measurements/` bind the exact NRS 484B.223(3)(b) requirement to the source-bound `measure_entry_to_turn` method. All five pass the pinned measurement-contract validator and synthetic saved positive processing; removing `native_samples.jsonl` is rejected in all five negatives. The 199/200-foot source intervals still cross the threshold. These are measurement diagnostics, not `runtime.py compatibility-recipe` receipts, Native physical observations or delivery case selections.

## Exact unselected CPU construction bundles

`draft-execution-manifest.json` now contains five exact case IDs, each with a primary and three structurally distinct fallbacks. The start-position, tracking-lookahead, and camera-framing changes have separate measurable Native or pixel triggers. `native/runner.py` requests the same authored center-turn-lane cell and records original body/pose/control and four synchronized lossless camera sources; it has not been run in CARLA. The ordered footprint extraction has a dedicated perimeter-order CPU regression test. All 20 bundles pass pinned `runtime.py offline`, 12 tests each. `audit-draft-offline.py` independently verifies exact source hashes, measurement contracts and receipts; `audit-draft-comparison.py` holds law, cell, actor, map source, camera contract, rate and duration fixed across the five commanded distance probes. These are draft construction checks, not exact compatibility or Native physical proofs. No case is selected.

## Full-duration saved source diagnostics and calibration

The source-bound turn detector now waits for a negative Native-Y heading change on the observed left-turn connector; the earlier lane-change heading cannot satisfy turn onset. The route request was calibrated against first full-body contact, with the original source-frame interval determining the measurement. The five 480-frame synthetic positives produce 180-foot within, 220-foot above, 199-foot within, 200-foot unresolved, and 201-foot above interval relations. Each passes original trace/evidence/body/frame joins, four source-video decodes, its measurement contract and Native attempt validation; each validator result requires rebuild. Removing `native_samples.jsonl` or replacing the connector road ID is rejected for each case. An independent saved audit recomputes cumulative path intervals from the original synthetic samples and holds map, x/time/frame trace, rate, duration and camera setup fixed across the five probes. These are synthetic CPU diagnostics; all cases remain unselected and physically unverified.

## Exact package synthetic diagnostic continuation

Five source-bound unselected proposal rows now permit the pinned package command to assemble its validation request. A 480-frame synthetic witness passes Core conversion, decoder, render and final decode. All 20 primary/fallback bundles pass exact pinned v1 package positives with full-resolution source videos and missing-`native_samples.jsonl` packaged negatives. The independent 20-row audit verifies current construction/runtime hashes, source and analysis hashes, four 480-frame source audits, final decode, negative logs and no acceptance claim. Saved processing and the five-case comparison pass after full-resolution fixture support. These are software diagnostics; strict v2 recipe receipts, physical Native lane/design and route proof, scenario-specific graphs and independent delivery acceptance remain worker-owned. The assignment stays blocked and unselected. Log hashes are in the latest RETURN-REPORT section.

## Source-bound fallback trigger continuation

`native/fallback_triggers.py` is embedded in all 20 current exact candidate bundles. It evaluates fallback1 from original Native body placement and full-body center-lane entry by 3 s, and fallback2 from the maximum original pose-to-requested-route distance against 0.35 m. Fallback3 consumes an independent per-frame review of original approach pixels; it binds annotations to the source video SHA and fails closed when review is absent or stale. Three synthetic tests exercise trigger and rejection paths in every pinned offline bundle (17 tests per bundle). `audit-fallback-triggers.py` independently checks embedded source and test identity in all 20 bundles. This proves the trigger logic and source-binding on CPU; it does not assert actual Native motion or original pixel observations.

The rebuilt 20 bundles pass pinned offline and independent offline/comparison audits. All 20 refreshed exact v1 synthetic package positives and missing-source negatives pass the independent package audit, including 480-frame source, Core/render and final-decode checks. The current manifest SHA is `d80f0ac76b71ceb3047df2f72d55a18a2e3ec9cea40ddcd8cf05539b117d3137`; offline summary SHA `93101959f0bcfc033d130e9ed01c4739d2cc0d8dee24f7472cc7aecf2ed660ba`; trigger audit SHA `f743cb65090e8e6a07829abec97d188246956fb1e603d381f544e9555a230bd0`; package audit SHA `be8dbbf110e5706538fab4bbed6cb699b75e3a3116e8998ad59c39554f8dd710`. Strict v2 receipts, physical Native lane designation/route proof, reviewed original pixels, and selected delivery acceptance remain absent. All five cases remain unselected and the assignment remains blocked.

## Native saved closure continuation

The current runner closes all four lossless encoders, records their zero exit codes, restores the world, composes the four source views, seals the original capture and records Native exit. The saved finalizer verifies the sealed source inventory and hashes before granting Native provenance. Unsealed or diagnostic fixtures retain `synthetic_local_diagnostic` and cannot claim a Native attempt or completed maneuver. A 480-frame diagnostic path passes composition, sealing, saved closure and finalization; changing a sealed Native sample is rejected by both closure and finalization. This is a synthetic CPU proof only (`native-closure-synthetic.log` SHA-256 `42ca9403a2d11621ac7f8b07877397c021c7b3bbdf993d8db8c7318377efdb90`).

All 20 current exact primary/fallback bundles pass pinned offline and independent source and controlled-comparison audits. The refreshed manifest, offline summary and independent offline audit SHA-256 values are `d3d76a3ba609610aaa7a11da8547c6b0e97cb1f34798212a5c6aa886c848cbe2`, `8f28156113f97d3626b5469a7ff3563ee6c04b4d4e5f480357c1eabe981108eb`, and `01fb9d596c3f1807ab78120832ff452cc4db9051339c28a3842d5403a0ce9cdd`. Five 480-frame saved positives and ten negatives pass, with independent saved comparison. All 20 refreshed full-resolution exact v1 package positives and missing-source negatives pass; the independent package audit SHA-256 is `6f8b37cdd8e725ac168918d2683e55255e2dfedbda596eccf1653ac769c743db`. These hashes supersede the preceding draft receipts.

The authored road now encodes exactly one center lane as OpenDRIVE `type="bidirectional"` with `left_turn_only_both_directions` usage metadata. The Native survey requests and checks the bidirectional lane type; three CPU tests prove the source shape and positive/negative mock readback. `native_center_lane_design_verified` stays false until independent saved source and pixel review. Authored geometry and controlled route audit pass; geometry audit SHA-256 `264d01346969855502d75ab04883df5deee807aeb8fa71ea38e2e30ddebe7fc1`. The frozen Core map projection currently omits the bidirectional lane key `(1, 0, -1)` (15 regions, 11 lane keys), and the exact v1 converted trace has no center-lane region at the surveyed point (reproducible CPU log SHA-256 `3487b295accfa7a4353d89220fa6a134326236df531dc1defcfb2110fcb2cac6`). Exact v1 package processing passes, but that does not establish the required center-lane Core structure or semantic stage validation.

All 20 rebuilt exact unselected bundles pass pinned offline with 20 tests each and independent source, controlled comparison and trigger audits. Current manifest/offline summary/offline audit SHA-256 values are `29ef3b20a938c1a463b5cd9286f9a618f53b7821e359c9ae8fb2a8ac1838b517`, `94fee44c80efbb735fa9164b6d227f743c02246b68a63e590281398ddd4e0cb7`, and `709924d69b707041f3a2a53ab643ad4ec345f7ac9a981208e6a28678df0946fd`. All 20 current full-resolution exact v1 package positives and missing-source negatives pass the independent audit (SHA-256 `b56511ff8333180514176b19aef441700c2f51dca83eef29cb17bc97307d95bd`). Five saved positives and ten negatives still pass. The current synthetic sealed-closure proof SHA-256 is `0d6e25eb8792e29a1799d0c55e7c81a6212074273052d60ad4aa411022e9ff9b`.

Strict selected v2 compatibility, original Native route and pixel observations, statutory runnable closure, center-lane Core semantic representation, independent selected delivery audit and an ordered GPU queue row remain worker-owned. The assignment remains blocked and unselected.
