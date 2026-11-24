# LVMC-11-46-030 at C394563

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `school_crosswalk`.

Exact statutory source: LVMC 11.46.030. The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Warning-triggered stop and continued restraint pending an alternative release..

Controlled planning variable: `warning_stop_distance_ft`. Proposed requests: stop 55 ft before warned school lane and wait for release; stop 40 ft before same warned school lane. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: signal-device/flagman/other-person warning; remain stopped until one of stated releases.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Exact Native runner and source acquisition, pinned-runtime offline/compatibility/process-saved, fallbacks, and independent audits remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 school-warning construction and measurement checkpoint

`.venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, no simulation). The statute requires a stop not less than 50 feet from the nearest side of a school pedestrian lane when a stationed signal device, flagman, or other person warns that children are about to cross or are crossing. Proceeding requires one of the stated observed releases. The two existing cases remain `planned_only`; 55 and 40 feet are requested centre-stop targets, not observed legal outcomes. The statute does not name the vehicle reference point, so front, centre, and rear distances are preserved.

`measure_school_warning.py` SHA-256 `30304a5bddde6747b48c647965f321fb3e0628250d9129cde983f9de956341e2` measures a complete 600-frame, 20 Hz source-shaped Native trace joined to four cameras. It requires school-lane, vehicle, warning-actor/state, and child-context source hashes; reports first cessation, all three stop distances, observed release and subsequent movement, and flags proceeding before an observed release without declaring legal compliance. `school-warning-measurement-contract.json` SHA-256 `b5a1f8ae6a41be8f7f74d127ab402c0d4bfa8102c7a7fc99882643b763b71479` maps all nine source observation terms.

`school_warning_scene.py` SHA-256 `d0d8efd36cf09e28e2348b9f27e979f2adff90ed26e66fb7f01369d5b9301375` specifies a two-way OpenDRIVE road, school-lane boundary, warning device and child actor requests, four source-camera views, and a controller that holds until a sourced statutory release. The requested stop station is the only scene difference. It does not assert that an installed prop is a legally stationed signal or that the requested child actor has verified age/status.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_school_warning.py` passed requested 55/40-foot stops, flagman-go release, and early-proceeding contexts plus eight negative source/trace checks. `school-warning-proof.json` SHA-256 `a77919f40e80851af039b9c760bc78b52a968a5993e28da937fcc7850d3eb81e`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_school_scene.py` passed two authored-scene positives and six negatives. `school-scene-proof.json` SHA-256 `2ea3b62a012c2bfa9e6c8fb56f6ca84ba17ce00be422d2a765031253ef9c3ab3`.

Next CPU work: wire exact Native runner and saved source acquisition, select first case, pass pinned-runtime offline/compatibility/actual process-saved, then test all release alternatives, fallbacks, independent audits, proposals, and manifest. Keep partial until assignment-scoped strict acceptance passes.
