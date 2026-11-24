# Current CPU checkpoint — 2026-11-23

The two planned comparison probes remain unselected and the package remains partial. The current frozen assignment source is `inputs/training__C111271__NRS-484B-310-1__motor_vehicle_driver/assignment.json`, SHA-256 `f16e6159019fe748ffc89f204e5a37cb1a856fef5cd503511ff7cacff8027bfe`.

`native/controller.py` now provides a CARLA-free policy proposal for pre-reference braking, a 30-frame engineering hold, and a common conflict gate for both probe cases. `native/runner.py --check` exercises the policy and validates the exact 600-frame, 20 Hz, four-camera source plan. This is an offline check, not a capture implementation or observed compliance.

`native/prove_source_measurement.py` generates six retained synthetic Native/frame-map/geometry traces under `.runtime-work/c111271-source-measurement/`, measures both stop and nonstop probes under each statutory stopping-reference hierarchy (marked limit line, nearest crosswalk, then intersection where neither exists), and rejects four damaged or missing sources. All traces contain 600 joined frames. The comparison keeps conflict occupancy cleared before either crossing so the stop policy is the controlled difference. The resulting proof is `native/source-measurement-proof.json`, SHA-256 `881e408357a672d15d10b4387311594b3216fbe28f40f254126d1f801bb908e5`. `native/measure.py` reports pre-crossing halt runs and conflict frames after crossing; its 0.05 m/s halt threshold is an engineering detector, not a statutory cutoff.

Commands and results: `.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python native/runner.py --check` passed; `.venv-cpu/bin/python native/prove_source_measurement.py --proof native/source-measurement-proof.json` passed six positive and four negative checks; `.venv-cpu/bin/python worker_check.py --assignment training__C111271__NRS-484B-310-1__motor_vehicle_driver --complete` passed static checks. The same scoped command with `--require-delivery-ready` failed because the package truthfully remains partial.

Next CPU work is the original Native CARLA scene and observed facing flashing-red source, limit-line/crosswalk geometry and body footprint, four source cameras, current-runtime exact offline and compatibility receipts, source-only saved processing, fallbacks, semantic proposals, and independent delivery/comparison audits. Neither original Native signal behavior nor pixels, physical completion, or legal judgment has been verified.

---

# NRS-484B-310-1 at C111271

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `flashing_red_signal`.

Witness branch: Flashing red at an intersection.

Comparison variable: `flashing_red_stop`. Proposed physical probes: stop at applicable boundary before proceeding; cross boundary without stopping. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C111271__NRS-484B-310-1__motor_vehicle_driver/assignment.json`, SHA-256 `33e36a1b3c7d1ced7f45b9cd457dba525c11d7a197a1a562836b2f5cc12b71d7`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
