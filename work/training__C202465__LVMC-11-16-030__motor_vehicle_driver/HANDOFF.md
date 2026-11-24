# training__C202465__LVMC-11-16-030__motor_vehicle_driver

Status: partial. A source-shaped rail-sight and speed proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/rail_sight.py` measures 600 synchronized 20 Hz samples over a grade-crossing approach and traversal. It checks the final 100 feet (30.48 m), two rail sight extents of 400 feet (121.92 m) each, speed against the 15 mph (6.7056 m/s) source value, and source states for a flagman and a visible inactive crossing signal. It requires changing observer-pose sources through the approach. These are measurements and diagnostic speed requests, not proof of a real governed crossing or unobstructed view of actual rail traffic.

`native/prove_rail_sight.py` passes a 30-second synthetic route/ray fixture and rejects missing frames, broken time join, absent ray source, static observer source and missing railway provenance. Proof log: `native/rail-sight-proof.log`, SHA-256 `9dd5843ac8708c7f287f402026d47b87f934ae92004c2655e724cfb1e33a060e`. Analyzer SHA-256: `f38c2fb24286093f0c62c799a956c791397bf361fbef5290a215b1f40405edd2`; proof SHA-256: `76c8d14961ab8f2b515e075172201013a36bff05d702f9c59bc90a6b30718a7e`.

Next CPU work: bind actual rail crossing and railway traffic to dynamic Native sight rays in both directions, including exception actors/devices; build the exact comparison with four source cameras and physical-risk fallbacks; prove offline, compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Leave planned cases unselected until these pass.

Exact law: The prima facie speed limit shall be fifteen miles per hour when traversing a grade crossing of a steam, electric or any other motor railway, if during the last one hundred feet of the approach to such crossing the driver does not have a clear and unobstructed view of such crossing and of any traffic on such railway for a distance of four hundred feet in both directions along such railway. This Section shall not apply in the case of any railway grade crossing where a human flagman is on duty or clearly visible electrical or mechanical railway crossing signal device is installed but does not then indicate the immediate approach of a railway train or car.

Selected witness scope: Crossing traversal under the stated sight conditions without either exception.. The case plan inventories 3 source topics and drafts one controlled comparison on `traversal_speed_and_crossing_sight`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Build a real railway grade crossing, crossing traffic sightlines in both directions at 400 feet throughout the last 100 feet, 15-mph traversal, and flagman/device exceptions.

Legal limit: A static straight ray or decorative railroad prop cannot establish the required visibility cause and governed grade crossing.
