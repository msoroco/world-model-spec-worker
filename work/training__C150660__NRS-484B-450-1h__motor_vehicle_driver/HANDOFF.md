# training__C150660__NRS-484B-450-1h__motor_vehicle_driver

Status: partial. A source-shaped safety-zone geometry proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/safety_zone_geometry.py` measures a 600-frame, 20 Hz stopped-vehicle footprint relative to a sourced safety-zone near edge, adjacent curb and both curb points opposite the zone ends. It uses the exact 30-foot conversion, 9.144 m, as a measurement boundary. It reports both the between-zone-and-curb branch and endpoint-distance branch without deciding whether a source map legally establishes the safety zone or whether a general stopping exception applies.

`native/prove_safety_zone_geometry.py` passes a 30-second synthetic map and actor fixture and rejects missing frames, broken time join, missing stop-state source, missing zone source and degenerate footprint. The map, stop and position observations are diagnostic only. The proof log is `native/safety-zone-geometry-proof.log` (SHA-256 `5fb54965ff35eb0f22ba6a16cb70003b1b271d092dc3fb053d117c4a64c389c7`). Analyzer SHA-256 is `3f9ed19b527680387a4496fe9cc92b7d12218fdc7decf2793ad2ba0bc149549a`; proof SHA-256 is `47898df7a6981937b259229f1d5db8790d5e4781cbd8c9d4a1014f6628558753`.

Next CPU work: bind the actual map and safety-zone designation, curb, vehicle footprint and stop-state sources to exact Native cases; separately acquire traffic-conflict, law, officer and device exception evidence; implement the controlled position comparison with fixed road and maneuver, four cameras and risk fallbacks; prove offline, compatibility, saved processing, semantic proposals and independent audits. Leave both cases unselected until those proofs pass.

Exact law: A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Between a safety zone and the adjacent curb or within 30 feet of points on the curb immediately opposite the ends of a safety zone.

Selected witness scope: Destination halt between zone and curb on a one-way road.. The case plan inventories 3 source topics and drafts one controlled comparison on `stopped_vehicle_position_relative_to_safety_zone`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Measure the stopped vehicle footprint between safety zone and curb, and curb distance from the points opposite both zone ends, including the 30-foot boundary.

Legal limit: Assess the general stopping exceptions independently; visual colored regions do not establish the zone.
