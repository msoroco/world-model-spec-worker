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

## 2026-11-26 exact Native request and saved-source checkpoint

The four cameras were aligned with the current runtime profile as `overview`, `approach`, `reference_corner`, and `driver_reference`. The scene, meter, contract and source-shaped tests use the same names. The source-shaped stop and scene proofs were rerun; both pass. These fixtures contain no original CARLA pixels.

`school_native_plan.py` now provides 600 frame, 20 Hz paired stop requests and a stateful controller. The controller requires an observed stop under warning before it accepts a sourced release; the requested release time alone never authorizes departure. `runner.py` is a prospective lazy-CARLA capture implementation: it requires reviewed school lane, child identity, warning asset and municipal source files before constructing actors, reads back Native poses and asset removal, captures four synchronized cameras, retains a frame map, seals source hashes, and restores the world. Physical motion, exact prop availability, child status, school-lane identity and camera pixels remain unverified.

`build_school_native.py` produces exact `probe_1` and `probe_2` primary and `fallback1` inline constructions under `draft-exact/`, bound in `draft-native-manifest.json`. The current primary construction SHA-256 values are `a833a9c13008a893e79e0fd82efea1c8e361d92c9fc91fef4b9c6f34b6d2b68d` and `afa5cf016b3a0c2f8b472b5b90a7fb314df0bc00423c34533542ff7d3321631c`. The fallback retains each exact case and capture contract while scaling controller throttle from 1.0 to 0.8 for a source-measured stop-station miss over 2 feet. Pinned `.venv-cpu/bin/python -B runtime.py offline --manifest work/training__C394563__LVMC-11-46-030__motor_vehicle_driver/draft-native-manifest.json --case CASE --candidate CANDIDATE --output .runtime-work/c394563-offline-SUFFIX-CANDIDATE-v7 --python $PWD/.venv-cpu/bin/python` passes all four exact case/candidate combinations. `bind_school_offline.py` copied the four passing logs under `proofs/` and bound their hashes in the draft manifest. These are drafts, not selected delivery cases.

`finalize.py` derives measurements only from a sealed original source inventory, checks all four camera files, 600 Native and frame-map joins, and four copied review sources; it writes an explicitly unaccepted Native result. `audit_school_comparison.py` compares the two measured stop positions while checking fixed source hashes, warning/child/release timelines, role, and camera joins. The meter now recognizes seven distinct source-labeled release variants from signal device, flagman and other person, and rejects a role/release mismatch; only signal removal has an exact construction draft. `SCHOOL_LANE_REVIEW` supplies the source-reviewed local asset packet before Native capture; four CPU tests verify source staging and reject missing or stale authority. `cpu-school-tests.log` SHA-256 `3ddc1cdfdefee23e3984a2b38a631daedaa1be2e8ce621ae1d96e2eafa688431` records 26 passing positive and negative tests. The assignment-scoped `worker_check.py --assignment training__C394563__LVMC-11-46-030__motor_vehicle_driver --complete` passes with truthful `partial` status.

Next CPU work: bind a diagnostic recipe to each exact construction and run pinned positive/missing-source compatibility; test the actual `process-saved` path and physical/lifecycle checker; author independent delivery audit and canonical stage proposals; expand the signal-device, flagman and other-person warning and each statutory release variant into controlled cases or source-backed dispositions. Add risk-based fallbacks only where a concrete original Native failure trigger justifies them. Do not mark ready until the exact strict assignment gate passes.
