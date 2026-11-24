# training__C149498__NRS-484B-503__motor_vehicle_driver

Status: partial. A source-shaped loading timeline proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/passenger_loading.py` measures a 600-frame, 20 Hz loading episode from raw zone, speed, door, occupancy, passenger doorway and civil-time fields. It interprets explicit sign hours in a declared time zone, including intervals crossing midnight. It reports time in the marked zone, halt time, door time and observed transfer frames without deciding zone validity or expeditiousness. `audit_selected_pair` checks the planned loading/no-transfer comparison over 600 frames: zone, civil time, vehicle motion and door channels remain fixed, while transfer/occupancy channels change; the audit does not confirm a physical transfer. The 0.05 m/s halt classification is an engineering motion tolerance, not a statutory grace period.

`native/prove_passenger_loading.py` passes a 30-second synthetic sample and rejects missing frames, broken time join, missing occupant source, missing doorway source and missing sign source. Its paired proof also rejects a changed door, changed civil timestamp, transfer in the no-transfer branch, and an occupant change without transfer. Its sign, curb and passenger observations are labeled synthetic diagnostics. The proof log is `native/passenger-loading-proof.log` (SHA-256 `e1f862f22debffe2fa386fee27a60e1cc2c79f6f6a898c5edfac4f2995f4da9b`). The analyzer SHA-256 is `e26ef548d1029f05b99522ec86d5d03ebfb4934c03d9d37f6c1780eb4f9b6e7f`; proof script SHA-256 is `c866ba9b8e96ce80bbcf41db97ca55a580a6926acbe545fc194c3a70e6fb5204`.

Next CPU work: bind a real passenger curb zone, its sign and applicable regulations to Native source acquisition; implement the exact comparison of observed passenger transfer versus no transfer while holding zone, time, vehicle and halt fixed; add four source cameras, selected construction and risk fallbacks; then run offline, compatibility, saved processing and independent audit proofs. Leave both cases unselected until these paths pass.

Exact law: A person shall not stop, stand or park a vehicle for any purpose or period of time except for the expeditious loading or unloading of passengers in any place marked as a passenger curb loading zone during hours when the regulations applicable to such passenger curb loading zone are effective.

Selected witness scope: Actual passenger loading during effective hours. The case plan inventories 2 source topics and drafts one controlled comparison on `actual_passenger_loading`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Use an actual marked passenger curb loading zone with effective civil hours, stationary episode, door/occupant events and expeditious passenger transfer.

Legal limit: A stopped vehicle alone cannot establish loading; the statutory exception is purpose and duration dependent.
