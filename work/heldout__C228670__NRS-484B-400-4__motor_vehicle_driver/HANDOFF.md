# Handoff: heldout__C228670__NRS-484B-400-4__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a one-way highway onto a two-directional highway, the left turn must be made by passing to the right of the centerline of the highway being entered upon leaving the intersection, and the approach for the left turn must be made as close as practicable to the left-hand curb of the one-way highway.

Cell C228670: road / left_turn / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- One-way source highway to two-directional destination, left turn at intersection: compare measured approach body position relative to left curb with held departure.
- Compare destination body position right of entered centerline on leaving intersection with held approach.
- “As close as practicable” has no numeric legal cutoff; retain geometry, body footprints, feasible obstructions and alternative position measurements.

## Current checkpoint

Three cases compare measured approach body distance from the one-way road left curb with departure held fixed, and measured departure body side of the two-way road centerline with approach held fixed. Original four-corner footprints and map lines are required; no practicability cutoff is invented. Tests reject wrong road geometry, absent phases and changed held positions.

Implemented and CPU-tested: turn_geometry.py, turn_comparison_audit.py, turn_native_runner.py and turn_camera_capture.py, and turn_finalizer.py. The finalizer joins original footprints, trace and frame map, derives two measurement channels from retained sources, and rejects missing or changed source rows. The Native runner selects a connected one-way-to-two-way left turn, computes original map curb and centerline references, spawns and controls the subject, captures original four-corner footprints and four synchronized cameras, and seals original Native capture. The comparison audit now binds the original map source hash and rejects drift in the held position, including drift hidden by an unchanged side boolean. The `cpu-tests.log` SHA256 is `11f12f8bd199fa4b30fbc550f8b4f1900b23fac64d257b3e7e5ae035e13ba5a4` (10 passing tests). These measurements are descriptive engineering observations and do not establish physical visibility or legal compliance. Status remains partial.

## Exact next CPU work

1. Review the new case plan against exact law and source topics; complete any missing alternatives or exceptions while preserving fixed cell/actor scope.
2. Bind the CPU-tested Native construction and four-camera capture to exact config/construction bundles; add finalizer integration, three fallback constructions per case, offline/compatibility and saved-processing receipts, semantic proposals and delivery audit.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, then `runtime.py process-saved` on retained synthetic sources. Integrate the CPU-tested measurement and comparison audit with exact source bindings, and test independent delivery rejection paths.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C228670__NRS-484B-400-4__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C228670__NRS-484B-400-4__motor_vehicle_driver --complete`. The strict readiness gate still fails because this package is partial; do not mark ready until every exact case and fallback passes its source-bound proofs.

## Current exact primary proofs

All three selected C228670 primary cases have exact inline construction bundles, four named camera plans, retained-source measurement contracts, source-hashed synthetic diagnostic recipes, and successful pinned offline plus positive/missing-source compatibility receipts. `primary-proofs.json` binds each current construction hash and copied proof log/receipt. These fixtures establish software behavior only. Reproduce with `.venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/build_first_construction.py`, `.venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/build_first_compatibility.py`, `.venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/expand_contrasts.py`, then `runtime.py offline` and `runtime.py compatibility` for each exact case using the two probe manifests. The pinned Lean validator was `.runtime-work/c125714-validator/.lake/build/bin/adapterCheck`; `runtime/library` supplied the library.

The remaining CPU tasks are three distinct risk-triggered fallback constructions per case, saved-only processing proof, complete semantic proposals, delivery audit, execution manifest and exact strict gate. No physical or legal acceptance is claimed.

## Current fallback and saved-processing proofs

`candidate-proofs.json` records all 12 current primary/fallback exact offline and positive/missing-source compatibility passes (3 cases × primary plus 3 distinct risk-triggered fallbacks). `saved-candidate-proofs.json` records all 12 `runtime.py process-saved` passes on source-shaped synthetic fixtures. Each saved proof checks the original attempt file hashes before and after processing and rejects physical/legal acceptance claims. Run `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/prove_candidates.py` and `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/prove_contrasts_saved.py` to reproduce. The exact diagnostic comparison values also pass the independent approach-curb and departure-centerline audit. Remaining CPU work: canonical semantic proposals, independent delivery audit, finalized execution manifest and strict assignment gate.

## Latest checkpoint for lead

The exact two comparison pairs and negative changes to held departure position and original map hash pass `work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/prove_comparisons.py`; see `contrast-comparison-proof.json` and `contrast-comparison-proof.log`. Draft semantic proposals now cover relevance, law template, judgment observables, bindings and three case proposals under `proposals/`; `proposals/semantic-index.json` binds current source hashes. They still require canonical stage validation. The assignment remains **partial** because delivery audit, manifest, canonical proposal validation and scoped strict gate have not passed. Resume those CPU tasks before marking ready.

## 2026-11-11 semantic stage repair and updated CPU environment

The pinned CPU preflight passes with NumPy 1.26.4, FFmpeg/ffprobe and Lean/Lake 4.28.0 (`work/_shared/preflight-latest.log`, SHA256 `969f4b100c808ce2b727e5745ed55b7c818576f3f7ed48f7c93eb0526fb70639`). Repository tests pass, and the pinned runtime suite passes with `PYTHONPATH=runtime:runtime/scenario_pipeline` (`work/_shared/runtime-tests-latest.log`, SHA256 `c1c367f1ccc4ad5816751a8af85c92c09f50a3aacc38ef6d7ab8b977c39cd661`). Earlier missing-dependency diagnoses are superseded.

`proposals/cases.json` now gives the two measured observables the canonical `subject_behavior` kind with null setpoints, adds a shared semantic baseline that does not add a recording, and declares the original-source practicability judgment sweep `incomplete` with its missing feasible-position facts. `.venv-cpu/bin/python work/heldout__C228670__NRS-484B-400-4__motor_vehicle_driver/validate_semantic.py` validates all six stages and three selected exact cases and rejects a stale stage hash (`semantic-validation.log`, SHA256 `76781bbadb9584678ea0ac289d86ae8e7cc4fdd3cce685424bc3dd83c30753ca`). This is structural semantic proof, not a completed practicability grid or legal conclusion. Construction and finalization were unchanged, so the existing candidate and saved-processing proofs remain bound.

The scoped nonstrict `worker_check.py --assignment heldout__C228670__NRS-484B-400-4__motor_vehicle_driver --complete` passes (`worker-check.log`, SHA256 `13f0432af4e71c37e2ab5646b3051e89164d7e3c4501c9f2937471df1141ade4`). Status remains partial. Next CPU work: build an exact original-source judgment sweep, implement the independent source-bound delivery audit, bind the finalized execution manifest and its current hashes, and rerun all affected proofs followed by the scoped strict gate. Actual Native motion and pixels remain unverified.

The scoped strict gate was rerun after semantic validation; it exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). No ready status is claimed.

## 2026-11-11 independent saved-source diagnostic audit

`turn_source_audit.py` independently binds the original attempt to saved analysis by SHA-256 for road geometry, original body footprints, frame map and trace; checks consecutive source frame joins; recomputes the left-turn measurements; checks exact case identity; compares all four original/saved camera byte hashes and fully decodes each. `prove_source_audit.py` passes the three current primary saved diagnostics and rejects an altered body source (`source-audit.log`, SHA256 `74662ad5b8d2b3dade0d81127026e47770971b4d6d5589bd813d231f1f429fb7`; `source-audit-proof.json`, SHA256 `8e3ebc3ed0c5e4bd4d08bea8dcf73f09428755c7fb4f7d241acf80ef987bf295`). These are synthetic software diagnostics and do not establish actual pixels or the canonical physical acceptance protocol. Extend the audit to all selected candidate attempts and local promoted-byte lifecycle before readiness.

The scoped nonstrict gate passes after this addition (`worker-check.log`, SHA256 `13f0432af4e71c37e2ab5646b3051e89164d7e3c4501c9f2937471df1141ade4`); scoped strict exits 1 at truthful partial status (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`).

The saved-source diagnostic audit was expanded from three primaries to all twelve exact primary/fallback attempts. `prove_source_audit.py` passes twelve full four-camera decodes and the altered-body negative (`source-audit.log` SHA256 `e2422e1745d6f74e348c7dce83bdadb95455a8afc92c4d51510b6e5a57f329f9`; `source-audit-proof.json` SHA256 `04e924e6590b588ce2c14d6fb7024314f0988c7d759a16a7cd09365569abfa9e`). The earlier three-primary audit hashes are superseded.

The independent camera audit now also compares the decoded frame count of each source to the original frame map via `ffprobe -count_frames`. All 12 exact candidate diagnostics still pass (`source-audit.log` SHA256 `e2422e1745d6f74e348c7dce83bdadb95455a8afc92c4d51510b6e5a57f329f9`; proof SHA256 `04e924e6590b588ce2c14d6fb7024314f0988c7d759a16a7cd09365569abfa9e`). This supersedes prior audit log hashes.
