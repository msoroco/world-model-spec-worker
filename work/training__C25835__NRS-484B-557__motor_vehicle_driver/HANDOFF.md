# NRS-484B-557 at C25835

Actor: `motor_vehicle_driver`. Frozen cell: `blind_rail_crossing` / `cross_railway` / `stop_sign`.

Exact statutory source: NRS 484B.557. The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Stop followed by proceeding with obstructed sight lines.

Controlled planning variable: `stop_distance_from_nearest_track_ft`. Proposed requests: full stop 25 ft before nearest rail then proceed with due care; full stop 10 ft before nearest rail then proceed. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: 50-foot outer bound; 15-foot inner bound; official stop sign erected; due care after stop.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Exact Native construction, offline/compatibility and actual process-saved proofs, tested candidates, and independent audits remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 source-shaped implementation checkpoint

The source requires an official stop sign at a dangerous highway railroad grade crossing designated by the Department of Transportation or by local authorities with its approval. Train presence and a minimum stop duration are not statutory activation conditions. The statute does not select a front, centre, or rear vehicle reference point; the measurement preserves all three. The 25-foot and 10-foot centre positions are requested controller targets, not observed outcomes or legal verdicts.

- `.venv-cpu/bin/python runtime.py preflight` passed with `cpu_preflight_passed: true` and no simulation start.
- `rail_stop_measure.py` SHA-256 `edeaa02f620cc7f2e8ae1290ace0e02a2ae69c8d440bccd9e18f91e6d711acb2` measures a 600-frame, 20 Hz trace joined to all four source cameras. It requires source hashes for map, rail, vehicle extent, official sign, designation, and occluder; checks sign governance and authority; returns front/centre/rear stop distances, stop interval, proceeding, visibility, and train state. Due care and legal compliance remain unassessed.
- `rail-stop-measurement-contract.json` SHA-256 `64afe8c87cc3fd0ea8671cfb3d08fb3ed3942b5c0f14ef065ad86ca60cb05d73` maps all eight source observation terms without treating time-to-conflict as a due-care cutoff.
- `rail_stop_controller.py` SHA-256 `59b22a1b03ba9b41647c628189dac0431d8801a0a789aa8969ba80fc9535c88a` requests approach, braking, hold, and proceeding for both stop stations, then brakes again if sourced visibility is lost. Its hold interval is an engineering policy, not a statutory duration.
- `.venv-cpu/bin/python prove_rail_stop.py` passed two source-shaped 30-second positives and eight negative source/trace tests. `rail-stop-proof.json` SHA-256 `61efae1e402df041f8d8c93f3ad6273be298ae845a78c1768db2352b06e5a949`.
- `.venv-cpu/bin/python prove_rail_stop_controller.py` passed two controller positives and five negative policy tests. `rail-stop-controller-proof.json` SHA-256 `6605a36c4de9838acc4d2c172578da7d54a79c17301d0a2c6d3dfe901a2358b5`.
- `.venv-cpu/bin/python worker_check.py --assignment training__C25835__NRS-484B-557__motor_vehicle_driver --complete` passed the partial-package static checkpoint.

These diagnostics do not establish original Native motion, actual pixels, designation, due care, or acceptance. Next CPU work is exact Native construction and first selected case offline/compatibility/process-saved, then the remaining cases, fallbacks, audits, proposals, and execution manifest. Keep partial until assignment-scoped strict acceptance passes.

The construction request `rail_stop_scene.py` SHA-256 `eaa8f0d8f3842d8db77468729c7786daa3a5d77408368d4dc88e467fb9246317` now specifies a two-way OpenDRIVE approach, two rail prop stations, a stop-sign prop, an approach occluder, ego vehicle, and four source-camera requests. It checks that only the requested stop centre station differs between probe 1 and probe 2. `.venv-cpu/bin/python prove_rail_stop_scene.py` passed two positive and four negative authored-scene checks; `rail-stop-scene-proof.json` SHA-256 `25e1211ebedd5e4e385e93943dce79f3f31c571b0d34111d844641372b9a6969`. The scene remains an authored request. An installed blueprint, physical at-grade geometry, sign governance, administrative designation, visibility effect, and camera pixels require original Native readback. The package has no selected exact runtime offline proof yet.
