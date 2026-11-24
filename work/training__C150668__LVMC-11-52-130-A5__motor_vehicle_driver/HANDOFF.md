# LVMC-11-52-130-A5 at C150668

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_road` / `stop_stand` / `sidewalk_elevator`.

Exact statutory source: LVMC 11.52.130(A)(5). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: stopping or standing near sidewalk elevator.

Controlled planning variable: `sidewalk_elevator_clearance_ft`. Proposed requests: stop more than five feet from sidewalk elevator or chute; stop within five feet of sidewalk elevator or chute. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: directly in front; traffic conflict; police or device direction.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/stop_route.py` requests paired 600-frame / 20 Hz stops with the same feedback policy and different longitudinal stations. The source-shaped proof `native/stop-route-proof.json` (SHA-256 `e8a98f49c22877a60a502f42854d7beb90079eb8cfbb6578b612bd0a4a1539a2`) passes both requested stops and rejects movement during rest, wrong station and shortened capture. Its synthetic trace is not original CARLA motion.

`native/measure_fixture.py` and `native/measurement-contract.json` require a source-identified sidewalk elevator or chute, its side extents and orientation, containing sidewalk geometry, original vehicle footprints, 600 Native frame/time joins and four source-camera identities. The CPU proof `native/fixture-proof.json` (SHA-256 `52b856073090d386f7eb4733e36648f7feb1b7d90560957c44296c6b15781fbe`) distinguishes outside versus within the statutory five-foot side band and rejects seven source, fixture, camera and stop-history defects. Placeholder fixture hashes and synthetic traces establish no original physical facts. The distinct `directly in front` branch and traffic-conflict/police/device exceptions remain pending.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire CARLA capture and four cameras to the controller and fixture geometry, author exact constructions, cover the front and exception branches, run exact offline/compatibility/saved-only proofs and independent delivery/comparison audits, then run the scoped strict ready gate before promotion.
