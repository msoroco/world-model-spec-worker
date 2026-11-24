# NRS-484B-507-1 at C386328

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_road` / `park` / `freight_loading_zone`.

Exact statutory source: NRS 484B.507(1); with 484B.507(2). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Parking in an effective freight curb loading zone.

Controlled planning variable: `freight_zone_activity`. Proposed requests: stop in active freight zone for expeditious material loading; park in same active freight zone without material loading. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: passenger stop while actually loading; no interference with material-transport vehicle; zone hours.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Exact Native runner and activity acquisition, pinned-runtime offline/compatibility/process-saved, fallbacks, and independent audits remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 freight-zone construction and measurement checkpoint

`.venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, simulation not started). The statute permits expeditious material pickup/loading or unloading/delivery during a marked zone's effective hours; its temporary passenger exchange exception also depends on actual activity and absence of interference with a materials vehicle waiting or about to enter. No numeric duration is substituted for “expeditious” or “temporarily.” The two current cases remain `planned_only`, with requested material loading versus idle parking.

`measure_freight.py` SHA-256 `1604a02cfce7e9c499c36a99fa182c4d557671c125427c2aef15073967571863` measures a complete 600-frame, 20 Hz source-shaped Native trace joined to four cameras. It requires hashes for zone marking, sign/hours, civil time, vehicle identity, material and passenger activities, and materials-vehicle wait state. It reports observed frames for active hours, stopped zone occupancy, materials handling, passenger exchange, and waiting context. Interference and legal compliance remain unassessed. `freight-measurement-contract.json` SHA-256 `8bec788001a95afc2e61aedf6adc8450b937bb0998e2491e58f03966f4a2f26d` maps the ten source observation terms.

`freight_scene.py` SHA-256 `6bbda3edf6aa3c5b74e10bda0e1c1acbc966e0679711b3c1a33652cfc134d8c6` specifies a one-way OpenDRIVE road, right freight curb segment, parked vehicle, sign and material prop requests, and four source-camera views. Both probes hold road, zone, sign, vehicle, civil-time policy, and cameras fixed; only requested material activity differs. It cannot assert that an installed sign bears the required text, that props move, or that actual material loading occurred.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_freight.py` passed material-loading, idle-parking, passenger/waiting context, and inactive-hours positives with nine negative source/trace checks. `freight-proof.json` SHA-256 `e5949435cb907b21d76a709e9c0158cfe3bed6f26ca62a52b4039f92c18b994e`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_freight_scene.py` passed two authored-scene positives and four negative checks. `freight-scene-proof.json` SHA-256 `1b0f0a1da592ae2cb4eec052dc2e39b4f3f6303047f5720f836518475cffe218`.

Next CPU work: connect an exact Native runner, original sign/civil/activity acquisition, and saved measurement; select one case and pass pinned-runtime offline, positive/negative compatibility, and actual process-saved. Then complete passenger/no-interference branches, fallbacks, independent audits, proposals, and manifest. Keep partial until the assignment-scoped strict gate passes.
