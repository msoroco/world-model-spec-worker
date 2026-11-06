# LVMC-11-52-130-A11 at C110454

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `park` / `intersection_boundary`.

Exact statutory source: LVMC 11.52.130(A)(11). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Intersection proximity during parking. Planned comparison variable: `parked_footprint_distance_to_intersection`. Requests: vehicle parks outside the 15-foot intersection band; vehicle parks inside the 15-foot intersection band. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject stops, stands or parks within fifteen feet of an intersection.

Timing to retain: judged for every instant at rest inside the band.

Exceptions and numeric alternatives planned: when necessary to avoid conflict with other traffic; in compliance with law; in compliance with the directions of a police officer or a traffic control device; intersection boundary numeric boundary 15 feet.

Unresolved judgment or rule composition: the fifteen feet are measured to the intersection region's boundary, which is the prolongation of the roadway edges, not to the crosswalk or stop line. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: Authored CPU construction and eight unselected engineering plans exist, but no executable Native capture or exact offline/compatibility proof exists. Physical feasibility, statutory exceptions and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Same-cell construction continuation

`native/geometry.py` uses an authored two-way intersection and parking bay shared with C110454's NRS 484B.213(2)(b) proposal. Two controlled routes park at x=25.0 m and x=13.5 m with the same road, actor and y=-5.25 m bay. The proposed full-body nearest distances to the x=7 m intersection entry boundary are 15.4 m and 3.9 m, bracketing 15 feet (4.572 m). Authored pavement/body and independent XML/route audits pass. These are proposed geometry values; the actual Native map and body remain unobserved.

`native/measure_park.py` requires a source hash, 480 original-schema frame/time joins, four body vertices, a surveyed boundary marker, and 40 consecutive rest frames. Two 480-frame, 20 Hz synthetic saved fixtures have 80 parked frames each; the saved measurement and an independent pair audit agree on both distances. A missing Native-frame negative for each case rejects. Four CPU tests cover distinct candidate knobs, source-bound measurable fallback triggers, source tampering and frame-join damage. `engineering-drafts.json` holds eight distinct **unselected** primary/fallback plans for the two witness cases. Exact pinned offline and positive/negative compatibility, saved Core/Lean/video integration, physical Native observations, full statutory exception review, selected delivery audit and ordered GPU queue row remain worker-owned and unfinished. The assignment remains `blocked`.

Two case-specific `worker-measurement-contract-v1` proposals under `draft-measurement-contracts/` pass the pinned validator and synthetic saved value/hash verification. Their source-removal negatives reject. Generated 480-frame fixture packets stay under ignored `.runtime-work/`; the contracts do not claim original Native observations. Full selected acceptance and the other statutory dispositions remain open.

The planned below/at/above numeric branch now has additional same-cell routes at 3.9, 4.572 and 5.4 m nearest parked-body distance from the proposed intersection boundary. All three have 480-frame synthetic saved measurements and missing-frame negatives. The exact 4.572 m probe returns `boundary_unresolved` because body/map precision and 50 ms sampling cannot certify a legal exact-boundary outcome. These numeric cases remain unselected and lack exact construction bundles and compatibility receipts.
