# LVMC-11-52-070 at C385967

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_road` / `angle_park` / `angle_parking_designation`.

Witness branch: permitted angle-parking orientation.

Comparison variable: `angle_park_orientation`. Proposed physical probes: park front toward lawful traffic direction; park front opposite lawful traffic direction. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C385967__LVMC-11-52-070__motor_vehicle_driver/assignment.json`, SHA-256 `7e2ea624713eebcfbb8a5f65515fe98c43b02be4232ce507370ec96c707a6052`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact draft construction and CPU proof

The current frozen assignment hash is `fbd358a4a2f996803ab49730b88f8a3ab4b8d15d6781c35ce2df8c96766d1574`; the earlier source hash above is historical. `native/angle-bay-road.xodr` authors a northbound one-way driving lane, angle-parking bay and proposed sign. `native/angle_park.py` checks the exact case and source contract, 600 joined rows, parked center and speed, four camera geometries, and the sign of the front vector projected onto the lawful road tangent. It deliberately defines no statutory angular tolerance. The City Traffic Engineer's permission decision is a separate source requirement and is not inferred from the authored sign.

`draft-native/probe_a/construction.json` SHA-256 `c3b82d52c9351e8ac3ad7bf8ea379004e50db048e3d25bc60b6901fe0fe89efa` requests a front yaw of 45 degrees with the northbound flow. `draft-native/probe_b/construction.json` SHA-256 `63b12a4ea74f86954025982adc9a6eecde9c5564670712b26b0eee8fb192396a` requests 225 degrees against it. Both are 30 seconds, 20 Hz, 600 frames, with the same bay center, zero speed and four named source cameras. Pinned `runtime.py offline` returned `offline_passed: true` and `simulation_started: false` for both; see `native/proof-probe-a.log` and `native/proof-probe-b.log`. `native/request-comparison-proof.json` SHA-256 `4d1e1eacb15d856c6c4b1621150afa5d9031250290d144ef4b8bc402352a0bc6` independently checks exact source hashes, road topology and the sole orientation difference.

These are unselected authored requests. They do not prove that angle parking is legally permitted at the place, that the sign exists in original Native observation, that the vehicle actually stood or parked in an angle bay, or that the original body front faces with or against lawful traffic. Native readback, permission evidence, four candidate compatibility recipes, selected process-saved fixtures and independent acceptance audit remain to be built. Status stays `partial`.
