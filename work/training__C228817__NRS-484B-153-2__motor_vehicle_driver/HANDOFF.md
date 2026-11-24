# training__C228817__NRS-484B-153-2__motor_vehicle_driver

Status: partial. A source-shaped door and passing-traffic proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/door_interference.py` defines two engineering door-request settings and measures 600 synchronized 20 Hz samples of a stopped vehicle, its traffic-side door segment, a boarding or alighting person and moving passing traffic. It reports door-open and transfer frames, minimum current door-segment-to-passing-vehicle surface gap and passing-vehicle deceleration. These observations do not decide whether moving traffic was legally interfered with.

`native/prove_door_interference.py` passes a 30-second synthetic fixture and rejects missing frames, broken time join, absent door state, nonmoving passing traffic and the wrong door side. Proof log: `native/door-interference-proof.log`, SHA-256 `8f4b737a289914e2ff9863cf9b9f362522c76837c3e386528a7bb820205da68e`. Analyzer SHA-256: `0fa9cc00da6b2f0f515d9a550b3105ab5f3d0baa0a5c7d2f47db58c32cf1515e`; proof SHA-256: `876e5ced7b2c92224256dca06333e93a1f3d4a7578ba4ff7823a7ff721e15dfc`.

The four accepted membership rows were checked against the supplied `review-context/review.json` and README. All list unresolved interference judgments and `receipt_sources: []`; no source-backed equivalence to the planned comparison can be established here. They remain accepted originals and are not replayed by this checkpoint. Next CPU work: complete source review if retained footage/trace becomes available; bind actual door, person and passing-traffic acquisition to exact Native comparison cases and four cameras; prove offline, compatibility, saved processing, fallbacks, semantic proposals and independent audits. Leave planned cases unselected until these pass.

Exact law: A person shall not open the door of or board or alight from the side of a vehicle which is closest to passing traffic in such a manner as to interfere with moving vehicular traffic.

Selected witness scope: Loading-task door opening, boarding or alighting beside moving vehicular traffic. The case plan inventories 2 source topics and drafts one controlled comparison on `door_or_alighting_interference`. Neither case has a Native realization or legal outcome.

The local snapshot lists 4 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Build a stopped vehicle adjacent to moving vehicular traffic; record closest-side door motion and boarding/alighting with resulting interference.

Legal limit: Opening a door by itself is insufficient; interference with moving traffic is the operative condition.
