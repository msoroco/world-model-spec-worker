# Handoff: heldout__C111305__NRS-484B-100__pedestrian

## Frozen scope

It is a misdemeanor for any person willfully to fail or refuse to comply with any lawful order or direction of any police officer while the officer is performing the duties of the officer in the enforcement of chapters 484A to 484E, inclusive, of NRS.

Cell C111305: intersection / travel / police_officer; actor pedestrian.

## Full-text branch inventory for CPU construction

- Officer gives an order or direction addressed to subject while enforcing chapters 484A–484E; compare observed compliance and noncompliance after indication.
- Whether officer status, duty and order lawfulness hold are sourced context/legal conditions; willfulness cannot be inferred from motion or a fixture.
- The statute applies to any person. Keep motor vehicle and pedestrian actor assignments separate while preserving the same text.

## Current checkpoint

Four cases: stop/proceed indications crossed with observed response/nonresponse. Timed indications, role/source context and original motion are checked. Comparison audit rejects changed officer, subject, actor or command; tests reject missing sources and legal/willfulness claims.

Implemented and CPU-tested: officer_response.py, officer_comparison_audit.py. The `cpu-tests.log` SHA256 is `abb9e14a2af39755f48af49e1992bb3b81624253d33b454303c7f2f167036eec`. These measurements are descriptive engineering observations and do not establish physical visibility or legal compliance. Status remains partial.

## Exact next CPU work

1. Review the new case plan against exact law and source topics; complete any missing alternatives or exceptions while preserving fixed cell/actor scope.
2. Exact Native pedestrian constructions, four-camera capture, finalizer integration, three fallback constructions per case, offline/compatibility and saved-processing receipts, semantic proposals and delivery audit remain CPU work.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, then `runtime.py process-saved` on retained synthetic sources. Integrate the CPU-tested measurement and comparison audit with exact source bindings, and test independent delivery rejection paths.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111305__NRS-484B-100__pedestrian --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111305__NRS-484B-100__pedestrian/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C111305__NRS-484B-100__pedestrian --complete`. The strict readiness gate still fails because this package is partial; do not mark ready until every exact case and fallback passes its source-bound proofs.

## 2026-11-15 exact Native pedestrian construction checkpoint

The four exact case IDs remain `__stop_responds`, `__stop_does_not_respond`, `__proceed_responds` and `__proceed_does_not_respond` under this assignment prefix. The selected pedestrian witness specifies a connected intersection approach and crossing route, an officer direction to wait at a named sidewalk location until release, an addressed recipient, modality and communication/opportunity evidence. `runner.py` now selects a bounded crosswalk with nearby sidewalk waypoints and junction center, spawns separate pedestrian and officer walkers, applies a timed officer arm pose and distinct post-direction walker controls, joins each original 20 Hz tick to four named camera sources and trace/motion, then restores world settings with readback. `config.json` and `construction.json` describe the root `__stop_responds` construction. All Native execution is still untested without CARLA; crosswalk selection and camera visibility must be independently observed in the first local run.

`officer_response.py` now requires exact direction text, recipient, wait-location source, communication modality/source and opportunity source, and rejects an asserted actual-perception conclusion. `officer_comparison_audit.py` holds those source conditions, actor, officer, subject and indication frame fixed across response comparisons; it rejects a changed wait location. The 9 CPU unit tests in `tests/test_officer_response.py` pass; `cpu-tests.log` SHA-256 is `9dae246cf6848862422f6010535a470dd5846326204293814ae14017fef6cb8e`. `runner.py --check` exits 0 from this package. `case-plan.json` now maps every original observation term to planned original channels, includes a four-view duration plan and all-case selected requirement disposition. The assignment-scoped nonstrict `worker_check.py --assignment heldout__C111305__NRS-484B-100__pedestrian --complete` exits 0. Status remains partial; no offline, compatibility, saved-processing or physical/legal result is claimed.

Next CPU sequence: implement the saved-only finalizer against original `officer_context.json`, `officer_direction.json`, `subject_motion.json`, `subject_motion_history.jsonl`, `video_frames.jsonl`, trace and all four source videos. First run root `__stop_responds` through exact offline, source-positive/missing-source compatibility and fresh saved processing. Then build the other three exact bundles and risk-based fallbacks, canonical semantic stage proposals, physical/lifecycle CPU proofs, independent delivery and fixed-condition comparison audits; bind hashes into a validated execution manifest, run the scoped strict gate, then the whole-batch strict gate. Actual officer authority, duty, lawfulness, communication, perception and willfulness remain unresolved original-source/legal questions. The CPU work above remains worker-owned.
