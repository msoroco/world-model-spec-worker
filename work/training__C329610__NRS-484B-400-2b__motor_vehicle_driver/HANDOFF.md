# NRS-484B-400-2b at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Exact statutory source: NRS 484B.400(2)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Left-turn exit onto a two-directional destination highway.. Planned comparison variable: `left_turn_exit_centerline_side`. Requests: driver exits intersection right of destination centerline; driver exits intersection left of destination centerline. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject has entered the intersection to turn left; both intersecting highways are two-directional.

Timing to retain: judged at the exit from the intersection: the footprint must leave right of the centreline; entry, then the turn, then the exit — the exit position is the test.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 4 membership rows; exact source-hashed equivalence and reuse are unverified.

Current gap: The unselected Native construction drafts and offline checks are described below. Exact positive/negative compatibility receipts, saved Core processing and independent delivery acceptance remain absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
# Source review continuation, 2026-11-05

The exact NRS 484B.400(2)(b) clause concerns the **exit** of a left turn, after intersection entry, on a two-directional destination highway. It differs from the C329610 (2)(a) approach-position assignment. The duplicate witness label was collapsed. `case-plan.json` now specifies the full-body exit event, a destination-centerline signed-position measurement draft, activation facts and three measurable construction risks. For the authored northbound destination, the right side is east of the destination centerline. The Native runner and saved proof drafts are described below; the result remains blocked.

## Exit geometry continuation

An authored same-cell map and two exit-side routes pass CPU pavement, route-continuity and prospective vehicle-body checks. A simple bicycle diagnostic follows both requested paths. The saved Native-frame measurement computes the complete vehicle footprint's side at the first measured full-body exit; positive right/left fixtures and negative incomplete-turn/two-way-direction fixtures pass. The wrong-side route traverses an opposing lane by design and has not been verified in Native CARLA. No selected runner, exact positive/negative compatibility proof, saved Core processing, or independent delivery audit exists, so the assignment remains blocked.

## Exact unselected draft continuation

The package now contains an observed-pose Native runner proposal, fixed approach and two controlled destination exit-side routes, four synchronized camera policies, a source-bound saved finalizer, five semantic stage drafts, and a measurement contract for each case. The full-body exit measurement rejects a reversed Native right axis. Two case IDs each have primary plus three distinct fallback construction bundles with measured triggers; all eight pass exact `runtime.py offline` checks with ten CPU tests per bundle. Independent bundle/source-hash and controlled-input audits pass. Semantic stage validation passes with the in-memory `law_record` to `law` alias necessitated by the separately documented frozen checker defect.

Both case IDs pass four-frame synthetic positive saved finalization, original-source hash checks, four source-video decodes, Native attempt validation, and a negative test removing `native_samples.jsonl`. The Native validator returns `rebuild_required: true`. These fixtures do not establish the full 480-frame pinned compatibility recipe, saved Core processing/render, independent delivery acceptance, camera-pixel coverage, wrong-side Native lane feasibility, or a legal outcome. The selected case count remains zero and the result remains blocked. Use `draft-execution-manifest.json`, the two audit scripts, `saved-fixture-proof.py`, and the hashes in `case-plan.json` to resume.

## Full-duration synthetic saved continuation

Both planned exit-side cases now pass 480-frame, 20 Hz, 24 s synthetic saved positive processing, measurement-contract verification, four source-video decodes, Native attempt validation with `rebuild_required: true`, and missing-Native-samples negative rejection. An independent saved audit holds the first 160 approach frames, map, law, actor, rate, cameras, channels and frame/time/y/heading trace fixed; it varies only the destination lateral exit and measures full-body right versus left exits. This does not establish CARLA physical feasibility, pinned-runtime Core/render compatibility, legal outcome or independent delivery acceptance. Both cases remain unselected and the result remains blocked.
