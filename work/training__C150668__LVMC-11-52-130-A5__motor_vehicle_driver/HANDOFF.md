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

## 2026-11-23 front and side-boundary CPU checkpoint

`native/prove_fixture.py` now tests the separate directly-in-front branch: stopped vehicle x-overlap with the fixture yields 500 front frames while the side-gap branch stays false. Exact five feet (`1.524 m`) counts inside the side band; `1.5241 m` does not. The meter uses a 1e-9 m absolute equality tolerance only for floating-point representation at the exact converted boundary. A sidewalk-chute fixture follows the same side-band geometry. Seven prior negative source checks remain passing. Refreshed receipt SHA-256 `ed5edb4ecbf27caa2c0c56f9cb79e674ac493cdcfb8a7ea5203fbd783d5ed566`; meter SHA-256 `7d5313e8242f1336593c17921e5efe4a41103d1976526f4e494063a8ae688ebc`; proof script SHA-256 `281fc3f2599f6d6c68025797116a3319220060040f604e07693ae34092dc3ed3`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c150668-front-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C150668__LVMC-11-52-130-A5__motor_vehicle_driver/native/prove_fixture.py`. Front orientation, original fixture/body geometry, traffic conflict/officer/device exceptions, Native capture, selected delivery and audits remain unfinished.
