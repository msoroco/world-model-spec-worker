# training__C177626__NRS-484B-263__motor_vehicle_driver

Status: partial. A source-shaped yield and gap proof is present; this is not a deployable delivery package.

## 2026-11-23 multi-traffic controller checkpoint

`native/multi_traffic_yield.py` now checks a complete 600-frame, 20 Hz trace against an explicit inventory of every approaching highway vehicle. It requires separate authority, lane, conflict-point and actor-inventory source identifiers, raw actor geometry in every frame, highway presence and approach flags, and observed ego yielding. It derives per-vehicle surface gaps, projected arrival gaps and through-vehicle deceleration, then evaluates the earlier and later engineering yield-request settings against identical hashed source rows. A present actor with unavailable arrival time conservatively retains the diagnostic yield request. The settings are not statutory hazard or safety definitions.

`native/prove_multi_traffic_yield.py` passed a two-through-vehicle entry/exit diagnostic and rejected a missing inventoried actor, an approaching vehicle off the highway, nonfinite raw geometry, a broken time join, no approaching traffic, missing controlled-access source, wrong lane identity and an unknown controller setting. The same source produced 340 earlier-policy request frames versus 0 later-policy request frames; this is a software comparison only. Log `native/multi-traffic-yield-proof.log` SHA-256 `a469b5fc9a858accfdec47ff1b5341c85ab6fc820b6a4a5a51b2e9923866533c`. Implementation SHA-256 `0c120f4813236aefcc5701d804903893cfeab5adafb006997ccf51368ed47511`; proof SHA-256 `feab9dcbb8ff289aa4c8f0e75ee3d86dd48699e76635a77c6bedf4ebe5298236`.

The case plan's two planned entry cases now state the actual comparison variable: engineering yield-request gap with the same network and traffic source. This does not select them for delivery. Next CPU work: bind a verified public-authority controlled-access source and actual access geometry to a Native construction; capture and retain all relevant highway traffic and four cameras; execute exact offline, compatibility, saved-processing, fallback and independent audits. Independently plan exit coverage because the fixed catalog maneuver is entry. No physical, legal or canonical outcome is claimed.

## 2026-11-23 CPU construction checkpoint

`native/controlled_access_yield.py` defines two engineering yield-controller settings and measures a 600-frame, 20 Hz trace of separate ramp and highway actors. It requires source identifiers for controlled-access status, distinct lanes and conflict point; measures surface gap, projected arrival-time gap, through-vehicle deceleration and observed yielding. The controller thresholds are diagnostic settings, not legal definitions of immediate hazard or reasonable safety. Entry and exit are explicit route kinds; a measured entry does not cover the exit branch.

`native/prove_controlled_access_yield.py` passes a 30-second synthetic actor/network fixture and rejects missing frames, broken time join, missing through-highway state, absent approaching traffic and missing network source. Synthetic speeds and geometry are diagnostic only. Proof log: `native/controlled-access-yield-proof.log`, SHA-256 `3cd5a3dcddc26628b9364877ae88ef87cbd95827c77161c7d7c1fa0c854df17f`. Controller SHA-256: `a9da7db70ef5cf60727b2792117f89f4bf5747df2c7db728a0d9d571ed06b5b6`; proof SHA-256: `4ec24e9c7edfa0c90c2d70199cb876924dec6d79616370732d2eddd1127d1ca2`.

Next CPU work: bind real controlled-access entry and exit paths and approaching highway traffic to Native construction; implement the exact controlled comparison and four-camera capture; run offline, compatibility, saved processing, physical-risk fallback and independent delivery/comparison audit proofs. Keep the planned cases unselected until those pass.

Exact law: The driver of a vehicle about to enter or exit a controlled-access highway shall yield the right-of-way to all vehicles approaching on the highway whose proximity constitutes an immediate hazard and shall continue to yield the right-of-way to that traffic until the driver may proceed with reasonable safety.

Selected witness scope: enter_paved_controlled_access_highway. The case plan inventories 2 source topics and drafts one controlled comparison on `entry_or_exit_gap_and_yield`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Build genuine controlled-access entry and exit paths with approaching highway traffic, conflict timing, yielding and safe-gap continuation.

Legal limit: Immediate hazard and reasonable safety remain judgments; one merge does not cover the exit alternative.
