# NRS-484B-400-2a at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Exact source: NRS 484B.400(2)(a). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Left-turn approach between two-directional highways..

Controlled variable: `approach-lane lateral position`. Requested pair: approach left turn near centerline in right half; approach left turn away from centerline in right half. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 2. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 4; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Blocker: No executable Native construction or four distinct candidates have been built; offline and compatibility proofs, measured-result finalization, positive/negative saved fixtures, independent audit and physical realization remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Both intersecting highways must be two-directional. Measure approach path in the right half nearest centerline before the left turn; the turn exit is not the target.

## Current source and measurement review

The two witness labels describe the same NRS 484B.400(2)(a) clause; the duplicate was removed from requirement dispositions. The plan now has a time scoped measurement contract draft, exact activation facts, required Native geometry and controller evidence, and three measurable candidate risks. This remains a draft. No selected delivery manifest, exact offline or compatibility proof, saved audit, or CARLA observation exists. The result remains blocked.

## CPU geometry continuation, 2026-11-05

`native/geometry.py` now authors a two-way orthogonal intersection with two lanes in each direction, a centerline, both left-turn connector links, and controlled approach positions at -1.75 m and -5.25 m. Its CPU check passed XML/link inspection, 0.3 m maximum route-sample spacing, pavement containment, and a prospective 5.2 m by 2.2 m body proxy for both paths. The command, source hash, and log hash are recorded in `case-plan.json` and `result.json`. Generated map and route samples are in ignored `.runtime-work/c329610-geometry-20261105`.

This is an offline geometry proposal. Native map loading, actual asset footprint, route completion, four candidate bundles per case, exact compatibility, saved processing, independent audits, and physical camera evidence remain unverified. The selected case count remains zero and the result remains blocked. The three fallback risks now have measured failure conditions and engineering changes, but are not constructed or tested.

The case plan also has a 20 Hz, 24 s synchronized four-view capture proposal and explicit Native/source-packet mappings for all eight source observation terms. The camera poses, duration sufficiency and packet production remain untested. The saved geometry prototype accepts only time ordered Native-shaped samples with a surveyed two-way geometry hash; its synthetic positive and four adversarial tests pass, but it is not connected to the runtime saved-processing path.
