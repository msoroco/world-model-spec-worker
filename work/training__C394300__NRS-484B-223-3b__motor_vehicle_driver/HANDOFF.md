# NRS-484B-223-3b at C394300

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `left_turn` / `center_turn_lane`.

Exact statutory source: NRS 484B.223(3)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Center-lane travel before a left turn from the highway. Planned comparison variable: `center_turn_lane_distance`. Requests: driver begins left turn within 200 feet of entering center turn lane; driver travels over 200 feet in center turn lane before left turn. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject is in a centre turn lane preparing to turn left from the highway.

Timing to retain: the distance is cumulative from entry into the lane to the start of the turn; the trace must cover both; the violation is the instant the accumulated in-lane distance passes 200 feet before the turn begins.

Exceptions and numeric alternatives planned: center turn lane travel numeric boundary 200 feet.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: Twenty unselected exact Native construction drafts, five measurement contracts, and full 480-frame synthetic saved finalization with two negatives per case now pass CPU checks and independent source/comparison audits. Exact pinned-runtime compatibility receipts, saved Core/render processing, physical Native center-lane designation and route evidence, independent delivery acceptance, and selection remain absent.

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
