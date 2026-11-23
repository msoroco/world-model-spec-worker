# testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.40.130 — It shall be unlawful for any person to operate a bicycle at a speed greater than is reasonable and prudent under the conditions then existing.
Assigned branch(es): Bicycle travel in an alley with a bicycle rack..
Cell: C10307 (alley, travel, bicycle_rack); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact law has no numeric speed boundary. `case-plan.json` now contains five controlled unlabeled exact cases: `__reference`, `__faster`, `__reduced_visibility`, `__pedestrian_near_rack`, and `__wet_surface`. Four comparisons reuse the reference and vary one authored dimension at a time. All retain alley travel, rack context, a human-powered bicycle subject, and an unresolved prudence judgment. The frozen evidence inventory has zero accepted recordings; its explicit gap is recorded in `evidence_review`. The exported judgment-range file has no key for this law and actor; no training speed bound was invented.

`speed_measurement.py` is a CPU saved-data checker for original Native frame map, bicycle velocity and contemporaneous context, with SHA-256 source binding and complete frame/time joins. It retains full measured speed history and leaves `legal_prudence` unresolved. `comparison_audit.py` checks exact case identities, original data, fixed context, measured speed or condition differences, and matching time coverage. These are draft worker-owned CPU components; they are not yet the pinned finalizer or canonical audit proof. Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator/tests -v`: 12 tests passed, log `cpu-measurement-comparison-tests.log` (SHA in `result.json`). The updated CPU preflight passed.

Next implement the exact alley/rack and bicycle runner, source capture and controller for all five cases; establish bicycle and jurisdiction source packets; author canonical semantic proposals and measurement contracts; run offline, positive/negative compatibility, saved-only and independent delivery/comparison acceptance proofs. Review whether any physical-risk fallback can preserve comparison isolation. Then run the exact strict assignment gate. Actual bicycle motion, rack pixels and camera coverage remain local GPU verification after CPU readiness.

A second measurement pass requires per-frame contemporaneous weather, surface, visibility, pedestrian and curvature history with exact original time joins. The saved CLI writes once and rejects overwrite. `measurement-contract.json` records the selected requirement, original source packets, units and limits. Fourteen focused tests passed after this change. The explicit next construction step is a source-backed alley OpenDRIVE and actual bicycle/rack blueprint inventory, then a lazy CARLA runner using the pinned capture and world-restoration helpers. No rack blueprint has been established from supplied assets, so a guessed prop ID must not be presented as a constructed rack.

## Alley geometry and source-gated actor construction

`authored-alley.xodr` is a worker engineering candidate, not a verified City of Las Vegas map. `native_geometry.py` checks its 80 m straight, 4 m wide travel surface, bicycle route and rack body envelope. The rack envelope is alongside the route outside the travel surface; the map check explicitly reports `rack_visual_asset_verified: false` and `municipal_jurisdiction_verified: false`. Its map SHA-256 is `ff78552ff664d8e706584d6cf296e08ccf496a9cb55e3b2e0a41b2bc764e2055`.

`native_spawn.py` requires a SHA-bound local Native blueprint inventory with both bicycle and rack IDs. It asks the actual world blueprint library for each ID, spawns both, reads back type and eight body vertices, rejects an absent/mismatched asset or out-of-envelope body, and destroys spawned actors on failure. The fake-world tests include missing rack and spawn-failure cleanup. The IDs in those tests are clearly fake; no actual rack blueprint or classification has been asserted. These components need integration with a lazy CARLA runner, pinned PipelineCapture, four-camera acquisition, finalizer and world restoration before any offline/compatibility proof can pass.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator/tests -v` passed 23 tests. The assignment `--complete` static check passed. The exact `--require-delivery-ready` check fails because the status is correctly partial.

## Measured Native route controller checkpoint

`native_controller.py` now applies a target velocity on each synchronous 20 Hz tick of the checked alley route. It retains actual frame IDs, poses and three-dimensional velocities; rejects a static/stalled asset after one second, lateral route departure, reversed motion, nonfinite readback, and endpoint noncompletion; and commands zero velocity on exit. This is an executable motion component, not a claim that a source-classified human-powered bicycle blueprint has been found or physically verified. `tests/test_native_controller.py` exercises successful full traversal, stalled body rejection, lateral departure and invalid start/target. The full assignment suite passes 27 tests; see `cpu-measurement-comparison-tests.log` and its SHA-256 in `result.json`.

`exact_case_target` now binds the controller to each of the five reviewed exact cases, rejects a foreign case identity and checks the assigned alley, bicycle and rack conditions before motion. The full suite passes 28 tests; the current log SHA-256 is in `result.json`.

The next CPU work is to source and seal an actual Native bicycle/rack inventory and classification, integrate `native_spawn.py` and this controller with the pinned four-camera capture and original frame map under world restoration, then author exact inline constructions and canonical proposals for all five cases. Add positive and missing-source compatibility, saved-only processing, physical-completion and independent delivery audit tests for each case. Keep the actual bicycle motion, rack pixels, camera visibility and episode quality for later physical verification. No external blocker has been demonstrated for these CPU tasks.

## 2026-11-24 original-clock and acquisition checkpoint

`native_controller.py` now reads every original Native world snapshot after its synchronous tick and rejects mismatched, skipped or non-20-Hz frame/time history. It records the actual elapsed time rather than a loop-index estimate. `native_acquisition.py` writes a once-only original frame map, bicycle motion and contemporaneous context packet with SHA-256 source inventory, then reads them back through `speed_measurement.measure`. The supplied context must equal its SHA-bound original packet; it cannot silently substitute an authored condition. This is CPU construction code and fake-world software proof, not an actual local bicycle/rack classification or physical recording.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator/tests -v` passed 33 tests; `cpu-measurement-comparison-tests.log` SHA-256 `be31fc36a192bca7e1f83e495e6820e73f947bba8a126d2bbc78abe58a59a5b7`. The assignment-scoped `--complete` static check passed (`cpu-static-check.log` SHA-256 `ba5fc03c965fa5607af895a01acf107e566a34ca2bcbed7fd88390f883c24cb1`). The exact `--require-delivery-ready` check returned exit 1 because this result remains partial (`cpu-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: verify the actual Native bicycle/rack asset inventory and municipal map source; integrate source-gated spawn, controller, original context capture, pinned four-camera capture and world restoration into exact case runners; author finalizer, proposals, offline/compatibility/saved-only proofs and independent delivery audit for all five cases. Keep physical motion, rack visibility and camera quality pending later local execution.
