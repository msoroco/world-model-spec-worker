# NRS-484B-450-1l at C229398

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `park` / `curb`.

Exact statutory source: NRS 484B.450(1)(l). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Parking on the highway side of a curbside vehicle..

Controlled planning variable: `highway_side_overlap_with_curbside_vehicle`. Proposed requests: stop beside curb clear of other parked vehicle; stop on highway side beside curbside parked vehicle. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: traffic conflict; lawful or police/device direction.

Accepted membership: 3 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 source-only CPU checkpoint

Pinned preflight passed: `.venv-cpu/bin/python runtime.py preflight`, exit 0, log `current-preflight.log` SHA-256 `5929cfc751f06630ee9c7966b7a90a9c6e5ffab5ed7995b42a7efda2cf60ab3e`.

`native/double_parking_meter.py` SHA-256 `6e57c7fc28c4779e3721fd297b0ee0f3236f1013c84ff2cd153b3f7d83230d17` is an executable saved-source geometry and halt meter. It requires surveyed curb endpoints, the road-interior side, and 600 consecutive 20 Hz original body-footprint frames for ego and curbside vehicles. It derives highway-side ordering, longitudinal body overlap, lateral body gap, concurrent rest/overlap frames, and longest run. It hashes both input sources in the returned diagnostic. The 0.03 m/frame stationarity tolerance is an engineering test parameter only. `native/measurement-contract.json` SHA-256 `07da08933686c8cc5707025bdb198ce89d60b40d608e76303773d0a26240fdff` names the additional Native, camera, actor, highway and exception sources still required. The source-observation mapping in `case-plan.json` now points to the measured outputs and explicitly leaves forced halt unassessed.

`.venv-cpu/bin/python work/training__C229398__NRS-484B-450-1l__motor_vehicle_driver/native/prove_double_parking_meter.py` passed, exit 0. Script SHA-256 `ce3eaf4a94f7c7b7a3006504362066b11e70c4b327fd41f5620623227db722b5`; proof log `native/double-parking-proof.log` SHA-256 `950fcf893edcfa8e410e863ade100b24d6aa4b12afcc5331880928ba10f3d70b`. The 600-frame synthetic source-shaped positive has 599 concurrent-rest-and-overlap frames; no-overlap, wrong-side and moving controls have zero. Missing curbside source and broken time join reject. Generated fixture files live under `.runtime-work/c229398-double-parking-meter/` and are not returned. These are CPU software observations only, not Native motion, camera pixels, accepted source equivalence, legal compliance or physical success.

Next CPU work: author and offline-prove an exact unselected Native curb/road construction and parking controller for each comparison arm; bind measured original footprints to the saved finalizer; capture and decode all four named source cameras; test positive/negative compatibility and process-saved for primary and distinct fallbacks; review accepted recording sources for actual equivalence; implement traffic-conflict, lawful, police and device exception branches and independent delivery/comparison audits. Keep `partial` until the assignment-scoped strict gate passes.

Assignment checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C229398__NRS-484B-450-1l__motor_vehicle_driver --complete` passed exit 0; `current-scoped-complete.log` SHA-256 `f5f99efe29163a6e352c074d69d62e11a7ebcbf56d3aaedcc8eded49d7f25f1a`. This static checkpoint is not the readiness gate. Assignment files pass size, trailing-whitespace and conflict-marker hygiene scans.
