# training__C110454__NRS-484B-213-2b__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.213(2)(b); with 484B.213(3). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 3}. No accepted equivalence receipt was verified.

## Planned controlled comparison

left-side driving approaching or traversing an intersection/rail crossing. Compare only `left_side_entry_distance_to_intersection` (ft) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Blocker and resumption

Executable Native capture package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native capture, four proven candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

## Statutory branch review continuation

`statutory-review.json` distinguishes two-way intersection approach and traversal, a grade-crossing alternative, and the one-way highway exception from the exact NRS 484B.213(2)(b)/(3) text. A source and status audit passes with `python3.11 work/training__C110454__NRS-484B-213-2b__motor_vehicle_driver/audit-statutory-review.py`. The frozen cell is an intersection with a parking maneuver; the current two requested distance probes do not establish that the vehicle is driven left of center. Three historical accepted IDs are membership-only, without an equivalence receipt. All four branches remain unproven, both cases remain unselected, and the assignment stays blocked. Next prepare same-cell geometry, Native body and road-direction measurements, and exact delivery candidates before any readiness claim.

## Native construction continuation

`native/geometry.py` now authors a two-way intersection, right-side parking bay and two controlled routes in the same cell. The corrected reference route finishes its proposed full-body left-side interval 34.1 m from the **intersection entry boundary**, outside the 30.48 m approach zone; the contrast interval reaches about 2.1 m from that boundary. The first geometry audit mistakenly used the intersection center as its distance reference. The corrected independent audit in `audit-native-geometry.py` checks the authored road, both routes, held endpoints and interval separation. All claims remain authored CPU geometry, without a Native map or physical vehicle observation.

`native/measure.py` checks source hashes, original frame/time joins, complete body footprints, observed movement and two-way road survey before returning a sampled distance relation. Eight CPU measurement/engineering tests pass. `synthetic-native-proof.py` runs 480-frame, 20 Hz source-shaped fixtures for each controlled route; they bracket the approach threshold and a missing-frame negative is rejected. These are synthetic local integration diagnostics. `engineering-drafts.json` contains eight distinct unselected construction proposals (primary plus three fallbacks for each case), with planned source-based triggers for route tracking error, parking endpoint speed and original pixel margin. Exact offline bundles, positive/negative pinned compatibility, Core/video fixture, independent delivery acceptance, statutory railroad/one-way alternatives and GPU queue entry remain worker-owned and unfinished. Keep `blocked` until those CPU proofs pass.
