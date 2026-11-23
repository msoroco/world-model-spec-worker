# testing__C110454__NRS-484D-165-4__motor_vehicle_driver

Status: partial executable headlamp measurement checkpoint. Three exact planned
cases are proposed; no original recording is claimed.

Exact law: NRS 484D.165(4) — Any lighted headlamps upon a parked vehicle shall be depressed or dimmed.
Assigned branch(es): Parked vehicle relative to intersection boundary.
Cell: C110454 (intersection, park, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Current exact coverage and CPU proof

The exact text has a parked-vehicle antecedent, a lighted-headlamp antecedent,
and the alternatives depressed or dimmed. `case-plan.json` names the exact
`__unlit`, `__low_beam` and `__high_beam` cases. The `lighted_applicability`
comparison holds the intersection scene, parking controller, vehicle, weather,
duration and cameras fixed between unlit and low beam. The
`dimmed_vs_bright_headlamp` comparison holds those same conditions between low
and high beam. These are requested CARLA light modes; they establish neither
emitted intensity nor legal meaning. A physical depressed-aim construction is
still missing and cannot be represented merely by a requested flag.

`lamp_probe.py` applies the requested CARLA light state lazily and reads back the
actual actor bits. Its source-bound measurement requires contiguous original
20 Hz actor and four-camera frame-map histories, sealed hashes, measured speed,
parking brake, reviewed-polygon footprint predicate and actor identity. The
0.1 m/s stationary probe is an engineering observation and does not define
statutory parking. `parking_geometry.py` calculates body-corner containment
against a reviewed Native parking polygon and reports intersection corner
overlap witnesses. `comparison_audit.py` rejects absent exact measurements,
missing source seals, altered fixed setup hashes, incomplete parked intervals
and wrong light-state readback. It does not check pixels or legal compliance.
The six focused tests include positive measurements and negative source,
camera, geometry and comparison cases. Run:

`.venv-cpu/bin/python -m unittest discover -s work/testing__C110454__NRS-484D-165-4__motor_vehicle_driver/tests -v`

The retained passing log is `cpu-lamp-tests.log`; its SHA256 is recorded in
`result.json`. Frozen `evidence.json` lists zero accepted recordings. The
`no-accepted-original-recording` gap in `case-plan.json` cites the exact frozen
assignment. No original emission, beam-aim, parked-status or camera claim is
made from these CPU fixtures. Each proposed case carries the physical risk of
unstable parking footprint or insufficient lamp visibility; a measured trigger
and tested fallback construction must be added to its exact manifest if a
reviewed Native site packet confirms that risk.

## Next CPU actions

1. Obtain a reviewed Native intersection site packet and implement a runner that parks the vehicle, records actual body corners, light-state readback, original camera frames and source hashes. Construct and test the depressed-beam-aim alternative if the pinned Native capability supports physical adjustment; otherwise retain its exact tested limitation without claiming that low-beam bits prove aim.
2. Build complete exact constructions and finalizer outputs for each case, then canonical semantic proposals, offline and positive/negative compatibility recipes, saved-only processing, independent delivery audit, and execution manifest with source hashes and risk-based fallbacks.
3. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110454__NRS-484D-165-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed in this turn. The focused
assignment tests passed 6 tests. The assignment `--complete` static check
passed, while the exact `--complete --require-delivery-ready` command failed
with `Preparation acceptance failed: partial/missing packages remain` because
`result.json` truthfully remains partial. See `cpu-static-check.log` and
`cpu-strict-check.log`. These software checks are not delivery proofs. CARLA is
needed only after the CPU package is ready, for actual motion and video review.
No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
