# C178759 / NRS 484B.650(1) / motor vehicle driver

Status: **partial**. Frozen cell: paved road, overtake right, other vehicle. Assignment source: `inputs/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/assignment.json` (SHA-256 `462017cc248d05f689e74d207d3afb650a0cfeefcdb2799662e80902f0a32f3a`). `evidence.json` lists zero accepted recordings. The witness asks for one continuous driver and one-mile event envelope containing a speeding act, two separate off-pavement right passes of the **same fixed other vehicle**, and immediate hazard. C228508 code supplied generic camera and route primitives only; no recording or fact was reused.

## Primary exact construction and CPU proofs

Case ID: `heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass`. `two_pass_construction.py` requests a first off-road-edge pass, reentry, lead reclaim by the same actor, second reentry and second off-road-edge pass. `transition_guard` checks signed ego/lead route progress and mapped edge clearance. `runner.py` fixes the overtaken Native actor ID, captures original 20 Hz route and actor geometry plus distinct mapped driving and outer-road edges, and records four synchronized RGB cameras. `paved_boundary.py` measures mapped geometry only; mapped road edge is **not** a determination of paved material. `right_pass_source.py`, `aggressive_sequence.py` and `two_pass_finalizer.py` join original frame/time/actor records and derive candidate order reversals and event-enclosing distance. Legal speeding, NRS 484B.210 exceptions, actual pavement, immediate hazard and the composite offense remain unjudged. The diagnostic fixture is software-shaped evidence, not CARLA motion or a physical/legal finding.

Current primary construction SHA-256: `c7e38089d1e09b65603efb2efd6a0c15b8158cf86740ed9e902d938a8830ae29`. Manifest: `execution-manifest.json`. Six local tests pass in `cpu-sequence-tests.log` (SHA-256 `14d2bd2c8125e3b533c40878c397d1ab8c89ccfd442a93cf835f72c82cf61041`). Exact offline passed in `repeated-right-pass-primary-offline.log`. Positive/negative Native compatibility passed in `repeated-right-pass-primary-compatibility.json`; removing `right_pass_sources.jsonl` is rejected in `repeated-right-pass-primary-negative.log`. Saved-only `runtime.py process-saved` passed with `originals_preserved=true` and `missing_evidence=false` in `repeated-right-pass-primary-saved-receipt.json`; its analysis revision binds the construction SHA above. The scoped nonstrict `worker_check.py --assignment heldout__C178759__NRS-484B-650-1__motor_vehicle_driver --complete` passed and is logged in `scoped-complete-gate.log`.

Reproduce the primary checks from repository root:

```sh
.venv-cpu/bin/python runtime.py offline --manifest work/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/execution-manifest.json --case heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass --candidate primary --output .runtime-work/c178759-repeated-right-pass-primary-offline-rerun
.venv-cpu/bin/python runtime.py compatibility --manifest work/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/execution-manifest.json --case heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass --candidate primary --output .runtime-work/c178759-repeated-right-pass-primary-compat-rerun --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck
```

For saved-only processing, materialize the exact case, materialize `diagnostic-recipe.json`, merge only missing fixture originals into the attempt, then run `runtime.py process-saved --manifest ... --case ... --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck`. `.runtime-work/c178759-primary-saved-v1-processing/v0001/processing.json` is the local source for the returned saved receipt.

## Remaining CPU preparation

1. Construct three genuinely distinct physical-risk fallback bundles for this selected case, each with exact offline, positive/negative compatibility and saved-only proof. Candidate risk triggers must be source-measured, not cosmetic flags.
2. Complete cross-law and one-mile branch coverage, below/at/above boundary probes and source-backed comparisons. Keep the fixed cell/actor and the same fixed overtaken vehicle.
3. Finish canonical semantic proposals, post-capture bindings, independent delivery and comparison audit code and rejection tests. Review the original law and frozen assignment independently before readiness.
4. Rerun all affected proofs after each construction or finalizer change; bind current hashes. Run `.venv-cpu/bin/python worker_check.py --assignment heldout__C178759__NRS-484B-650-1__motor_vehicle_driver --complete --require-delivery-ready` and mark ready only if it passes.

Actual CARLA motion, traversable pavement, camera coverage, physical completion and legal assessment remain operator/reviewer checks after CPU preparation. They are not claimed by this fixture. No GPU, NERSC or SQLite run occurred. No frozen input, runtime or batch file was edited. The separate timer handles Git checkpoints.
