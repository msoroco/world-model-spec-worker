# Handoff: heldout__C10365__NRS-484B-100__motor_vehicle_driver

## Frozen scope

It is a misdemeanor for any person willfully to fail or refuse to comply with any lawful order or direction of any police officer while the officer is performing the duties of the officer in the enforcement of chapters 484A to 484E, inclusive, of NRS.

Cell C10365: alley / travel / police_officer; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Officer gives an order or direction addressed to subject while enforcing chapters 484A–484E; compare observed compliance and noncompliance after indication.
- Whether officer status, duty and order lawfulness hold are sourced context/legal conditions; willfulness cannot be inferred from motion or a fixture.
- The statute applies to any person. Keep motor vehicle and pedestrian actor assignments separate while preserving the same text.

## Current checkpoint

Four cases: stop/proceed indications crossed with observed response/nonresponse. Timed indications, role/source context and original motion are checked. Comparison audit rejects changed officer, subject, actor or command; tests reject missing sources and legal/willfulness claims.

Implemented and CPU-tested: officer_response.py, officer_comparison_audit.py. The `cpu-tests.log` SHA256 is `abb9e14a2af39755f48af49e1992bb3b81624253d33b454303c7f2f167036eec`. These measurements are descriptive engineering observations and do not establish physical visibility or legal compliance. Status remains partial.

## Exact next CPU work

1. Review the new case plan against exact law and source topics; complete any missing alternatives or exceptions while preserving fixed cell/actor scope.
2. Exact Native constructions, four-camera capture, finalizer integration, three fallback constructions per case, offline/compatibility and saved-processing receipts, semantic proposals and delivery audit remain CPU work.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, then `runtime.py process-saved` on retained synthetic sources. Integrate the CPU-tested measurement and comparison audit with exact source bindings, and test independent delivery rejection paths.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C10365__NRS-484B-100__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C10365__NRS-484B-100__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C10365__NRS-484B-100__motor_vehicle_driver --complete`. The strict readiness gate still fails because this package is partial; do not mark ready until every exact case and fallback passes its source-bound proofs.

## Native construction progress, 2026-11-11

`officer_native_runner.py` now implements a connected narrow alley lane and adjacent sidewalk search, motor vehicle and walker spawning, a timed stop/proceed arm pose using CARLA walker bone control, all four predeclared post-indication vehicle control branches, original motion/context/direction retention, four source camera capture, frame joins, capture closure and settings restoration. `officer_camera_capture.py` retains the four original streams. Three new CPU tests exercise route selection, the four control branches and distinct pose calls; all eight assignment tests pass in `cpu-tests.log`. CARLA's published Python API documents `Walker.get_bones`, `Walker.set_bones`, and `Walker.blend_pose`; actual skeleton naming, visible gesture, alley geometry, officer identity and legal authority require original Native review.

The runner is not yet an exact executable package: there is no materialized config/construction or finalizer integration for any of the four cases. Next, build one exact case with source-bound finalization and positive/missing-source offline, compatibility and saved-only proofs; then expand the other cases and three fallbacks each, semantic proposals, lifecycle/physical fixtures, delivery and comparison audits. Keep result partial until the strict scoped gate passes.

## First exact construction and saved analysis, 2026-11-11

`runner.py`, `config.json` and `construction.json` now materialize the `stop_responds` selected case around the source-retaining Native implementation. `officer_finalizer.py` joins the original frame map, trace and motion copies, measures the timed direction and observed response, emits derived channels from original sources, and rejects missing or inconsistent sources. Two new tests exercise a valid source join and both missing-source and changed-frame rejection; all ten tests pass. The exact runner `--check` passes with the materialized config. Proof logs and hashes are in `result.json`.

This is an executable construction draft only. The semantic proposal chain, measurement contract, diagnostic recipe, execution manifest, three distinct fallbacks for each of four cases, exact offline/compatibility/saved proofs, physical protocol and delivery audits remain CPU work. No Native geometry, gesture visibility, officer authority, lawful duty or willfulness has been verified.

## Four primary proofs and fallback rebind, 2026-11-11

Four primary exact cases passed pinned `runtime.py offline`, positive/negative `compatibility`, and synthetic `process-saved` under the prior four-primary manifest; see `primary-proofs.json` and `primary-proofs.log`. These receipts are historical after the fallback/source rebind. `build_fallbacks.py` now binds current Native/camera source into the root and four inline constructions and adds three distinct alternatives per case: 12 m connected route for alley connectivity, 20 degree officer-arm pitch change for pixel legibility, and 2 m overview mount lift for source visibility. The runner consumes and bounds each knob. Current `probe-compatibility-manifest.json` has 16 exact candidate bundles. Ten CPU tests pass (`cpu-tests.log`); scoped `worker_check.py --complete` passes (`worker-check.log`). Current manifest candidate proofs and saved reproof are pending, as are semantic sweep, physical protocol, independent audits and execution manifest. No Native motion, actual pixels, lawful duty, order lawfulness or willfulness is claimed. Next run `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C10365__NRS-484B-100__motor_vehicle_driver/prove_all_candidates.py > work/heldout__C10365__NRS-484B-100__motor_vehicle_driver/candidate-proofs.log 2>&1`, then bind current receipts and continue the audits.

## Current pinned-runtime candidate proofs, 2026-11-11

`.venv-cpu/bin/python runtime.py preflight` passes with Python 3.11, pinned packages and Lean 4.28.0. `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C10365__NRS-484B-100__motor_vehicle_driver/prove_all_candidates.py` now passes all 16 exact candidate offline and positive/negative source-bound compatibility proofs, plus saved processing of all four primary cases. `candidate-proofs.json` binds current construction hashes to the exact logs and receipts. The four original camera streams were processed in diagnostic fixtures, not physically verified.

The proof script now uses fresh `-v3` ignored output paths because the runtime retains prior attempts; an initial rerun failed on an existing `-v2` directory, not on construction. Current logs are `candidate-proofs.log` and per-case files under `cases/`. Remaining CPU work: bind the passing receipts into `execution-manifest.json`, complete the source-backed judgment sweep and semantic index, add three physical outcome fixtures per case, run independent positive/negative delivery and comparison audits, and pass the scoped strict gate. Resume with the manifest construction and rerun any proof affected by source or construction changes.
