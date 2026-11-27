# training__C230222__NRS-484B-600-1e__motor_vehicle_driver

Status: ready for local delivery; the exact assignment-scoped strict CPU gate passed exit 0 on 2026-11-26. Three 30-second, 600-frame Native bundles request 78, 80 and 82 mph respectively. The request is a controller input; observed speed is acquired from post-tick Native velocity, with a separate source-bound measurement and uncertainty near the 80 mph boundary. No Native run, physical completion, legal verdict or accepted recording reuse is claimed.

## Exact source and historical membership

NRS 484B.600(1)(e) prohibits any person from driving or operating any vehicle at more than 80 mph in any event. The C230222 cell fixes road/travel/curb and motor_vehicle_driver. The three historical accepted membership rows have empty receipt_sources in the frozen review; they establish neither measured speed nor source equivalence and are not reused. Selected cases are `training__C230222__NRS-484B-600-1e__motor_vehicle_driver__probe_01`, `__probe_02`, `__probe_03`; the sole comparison is `training__C230222__NRS-484B-600-1e__motor_vehicle_driver__comparison`. Full-law branch and source-observation dispositions are in `case-plan.json`.

## Current-runtime CPU proofs

Each selected primary has exact offline, public compatibility positive and missing-native-motion negative, recorded-only saved processing, a synthetic physical preparation fixture, and independent delivery audit positive/missing-source negative. The 82 mph case also has a distinct tested fallback1 that changes only the speed controller gain. All three primaries pass source-independent semantic stage validation and the comparison audit's positive plus four adversarial tests. `delivery_audit.py` checks saved 600-frame source hashes and measurement outputs; diagnostic results are never treated as original pixels or physical completion. Root bundle tests and the separate seven-test saved-source speed meter pass. The latter uses a different diagnostic schema and is not substituted for selected Native measurement.

Execution manifest SHA-256: `a2be5ed51a240f1b41690b0019e8e7a58d415551f513687d48f743f07f6a3bd8`. Primary construction SHA-256: `d14cd66d6a2866bb449bd4bcb9ee3700816ea0cca904c965556e35a2a4d1a38a`, `8e8dc19216540753fed60298d95b9848d18dd45de20d3792f0d3248f10bfed29`, `f297013c2c8def8ca02c8a1f22789eafc1668184ca573861fee82cb7011a7658`. Fallback construction SHA-256: `2f8ed2aef22209041bd605ae1b11f3dd9656c9f9eb488114040f4bf977b45dfe`. Proof logs and receipts are bound in `execution-manifest.json`; scratch output remains under `.runtime-work/c230222/`.

## Next check and local delivery

The exact gate `SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c230222/pipeline .venv-cpu/bin/python -B worker_check.py --assignment training__C230222__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` passed exit 0. For local original capture, run the exact `first_gpu_delivery_command` in result.json with CARLA and job variables supplied, then independently review original Native motion, identity, all four camera videos, physical travel and legal applicability before acceptance. The synthetic CPU proofs establish software compatibility only.
