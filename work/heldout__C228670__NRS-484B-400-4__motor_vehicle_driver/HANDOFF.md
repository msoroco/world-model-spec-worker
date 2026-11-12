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
