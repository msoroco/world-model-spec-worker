# NRS-484B-400-2b at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Exact statutory source: NRS 484B.400(2)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Left-turn exit onto a two-directional destination highway.. Planned comparison variable: `left_turn_exit_centerline_side`. Requests: driver exits intersection right of destination centerline; driver exits intersection left of destination centerline. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject has entered the intersection to turn left; both intersecting highways are two-directional.

Timing to retain: judged at the exit from the intersection: the footprint must leave right of the centreline; entry, then the turn, then the exit — the exit position is the test.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 4 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
# Source review continuation, 2026-11-05

The exact NRS 484B.400(2)(b) clause concerns the **exit** of a left turn, after intersection entry, on a two-directional destination highway. It differs from the C329610 (2)(a) approach-position assignment. The duplicate witness label was collapsed. `case-plan.json` now specifies the full-body exit event, a destination-centerline signed-position measurement draft, activation facts and three measurable construction risks. For a northbound destination, the right side is east of the destination centerline. This is a statutory and measurement draft only; no Native case, fallback or saved proof was built. The result remains blocked.

## Exit geometry continuation

An authored same-cell map and two exit-side routes now pass CPU pavement, route-continuity and prospective vehicle-body checks. A simple bicycle diagnostic follows both requested paths. The saved Native-frame measurement prototype computes the complete vehicle footprint's side at the first measured full-body exit; positive right/left fixtures and negative incomplete-turn/two-way-direction fixtures pass. The wrong-side route traverses an opposing lane by design and has not been verified in Native CARLA. No selected runner, four fallback bundles, exact runtime offline/compatibility proof, saved Core processing, or independent delivery audit exists, so the assignment remains blocked.
