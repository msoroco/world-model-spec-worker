# training__C177626__NRS-484B-263__motor_vehicle_driver

Status: partial. A source-shaped yield and gap proof is present; this is not a deployable delivery package.

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
