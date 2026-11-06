# LVMC-11-52-130-A11 at C110454

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `park` / `intersection_boundary`.

Exact statutory source: LVMC 11.52.130(A)(11). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Intersection proximity during parking. Planned comparison variable: `parked_footprint_distance_to_intersection`. Requests: vehicle parks outside the 15-foot intersection band; vehicle parks inside the 15-foot intersection band. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject stops, stands or parks within fifteen feet of an intersection.

Timing to retain: judged for every instant at rest inside the band.

Exceptions and numeric alternatives planned: when necessary to avoid conflict with other traffic; in compliance with law; in compliance with the directions of a police officer or a traffic control device; intersection boundary numeric boundary 15 feet.

Unresolved judgment or rule composition: the fifteen feet are measured to the intersection region's boundary, which is the prolongation of the roadway edges, not to the crosswalk or stop line. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: Executable witness and numeric Native bundles with synthetic v1 package proofs now exist. Strict v2 fixture recipes, selected delivery audits, statutory exception case constructions and ordered GPU queue remain worker-owned unfinished work. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Same-cell construction continuation

`native/geometry.py` uses an authored two-way intersection and parking bay shared with C110454's NRS 484B.213(2)(b) proposal. Two controlled routes park at x=25.0 m and x=13.5 m with the same road, actor and y=-5.25 m bay. The proposed full-body nearest distances to the x=7 m intersection entry boundary are 15.4 m and 3.9 m, bracketing 15 feet (4.572 m). Authored pavement/body and independent XML/route audits pass. These are proposed geometry values; the actual Native map and body remain unobserved.

`native/measure_park.py` requires a source hash, 480 original-schema frame/time joins, four body vertices, a surveyed boundary marker, and 40 consecutive rest frames. Two 480-frame, 20 Hz synthetic saved fixtures have 80 parked frames each; the saved measurement and an independent pair audit agree on both distances. A missing Native-frame negative for each case rejects. Four CPU source tests cover distinct candidate knobs, source-bound measurable fallback triggers, source tampering and frame-join damage. `engineering-drafts.json` holds eight distinct **unselected** primary/fallback plans for the two witness cases. Strict v2 compatibility, physical Native observations, full statutory exception construction, selected delivery audit and ordered GPU queue row remain worker-owned and unfinished. The assignment remains `blocked`.

## Exact witness package continuation

`build-native-candidates.py` embeds the authored OpenDRIVE, route controller, four cameras, original-frame runner, parking-history finalizer and source-bound exception evidence gates in eight witness candidate bundles under `draft-candidates/{witness_1,witness_2}/{primary,fallback1,fallback2,fallback3}`. All eight exact `runtime.py offline` commands pass nine tests per bundle; `command-offline.log` and `offline.log` retain the evidence. The three fallbacks have separate lookahead, braking and overview FOV knobs with original Native or decoded-video trigger metrics.

`saved-fixture-proof.py` passes the 480-frame positive and missing parking-history negative for both witness cases. `probe-core-synthetic.py` passes Core, Lean and rendered-video processing with full frame joins for both cases. `probe-package-compatibility.py` passes all eight exact pinned v1 materialized packages, including saved analysis, Native validation, mandatory observations, Lean decoder, render, final decoded frames and unchanged acquisition; each rejects removal of `native_parking_history.json`. `audit-draft-package.py` independently checks construction hashes, offline logs, pinned measurement contracts, positive receipts and missing-source negatives; `draft-package-audit.json` passes. These are synthetic unselected diagnostics, not strict v2 compatibility or accepted Native evidence. Keep `blocked` until the required CPU selected delivery proofs and remaining statutory branches pass.

Two case-specific `worker-measurement-contract-v1` proposals under `draft-measurement-contracts/` pass the pinned validator and synthetic saved value/hash verification. Their source-removal negatives reject. Generated 480-frame fixture packets stay under ignored `.runtime-work/`; the contracts do not claim original Native observations. Full selected acceptance and the other statutory dispositions remain open.

The planned below/at/above numeric branch has same-cell routes at 3.9, 4.572 and 5.4 m nearest parked-body distance from the proposed intersection boundary. All three have 480-frame synthetic saved measurements and missing-frame negatives. The exact 4.572 m probe returns `boundary_unresolved` because body/map precision and 50 ms sampling cannot certify a legal exact-boundary outcome. `build-numeric-candidates.py` now produces twelve exact source-hashed numeric primary/fallback bundles under `draft-candidates/numeric_1_{0,1,2}/`. Every bundle passes the pinned offline command with nine tests and synthetic v1 positive/negative package compatibility. Each case passes 480-frame Core/Lean/video integration. `audit-numeric-package-comparison.py` independently verifies the twelve exact construction hashes and receipts, the three measured distances, unchanged law/cell/actor/capture/engineering settings within each candidate, and the unresolved exact boundary. The numeric cases remain unselected.

`build-exception-fixtures.py` constructs three controlled synthetic source pairs for traffic-conflict necessity, cited-law compliance, and police/device direction evidence. Each positive passes the source-hash gate and returns `requires_independent_review`; each one-field negative rejects. `audit-exception-fixtures.py` independently verifies pair identity, hashes and one changed source field. These prove source gate behavior only. They do not construct the physical exception scenes, establish exception applicability, or settle legal outcomes. All remain worker-owned.
