# testing__C110454__NRS-484D-165-4__motor_vehicle_driver

Status: partial executable Native headlamp source checkpoint. Three exact planned
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

`saved_lamps.py` consumes the sealed Native receipt and source hashes without CARLA; it rejects diagnostic-site data for delivery, changed original sources and case mismatches. Its output keeps emitted brightness, beam aim and legal judgment unresolved. `lamp_probe.py` applies the requested CARLA light state lazily and reads back the
actual actor bits. Its source-bound measurement requires contiguous original
20 Hz actor and four-camera frame-map histories, sealed hashes, measured speed,
parking brake, reviewed-polygon footprint predicate and actor identity. The
0.1 m/s stationary probe is an engineering observation and does not define
statutory parking. `parking_geometry.py` calculates body-corner containment
against a reviewed Native parking polygon and reports intersection corner
overlap witnesses. `comparison_audit.py` rejects absent exact measurements,
missing source seals, altered fixed setup hashes, incomplete parked intervals
and wrong light-state readback. It does not check pixels or legal compliance.
The sixteen focused tests include positive measurements and negative source,
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

1. Obtain a reviewed Native intersection site packet and integrate `native_capture.capture_interval` into the exact runner. The current lazy capture applies parking brake and requested light state, reads actual body corners/velocity/light bits from the Native actor, joins four original camera frames at 20 Hz, and seals actor/camera JSONL hashes. It rejects site-source tamper, frame gaps and stale/missing camera joins before emitting sources. Its CPU fake fixture proves software behavior only; the runner still needs actor spawning, world ownership and source pixel capture. The site polygons must match their sealed JSON source. Construct and test the depressed-beam-aim alternative if the pinned Native capability supports physical adjustment; otherwise retain its exact tested limitation without claiming that low-beam bits prove aim.
2. Build complete exact constructions and finalizer outputs for each case, then canonical semantic proposals, offline and positive/negative compatibility recipes, saved-only processing, independent delivery audit, and execution manifest with source hashes and risk-based fallbacks.
3. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110454__NRS-484D-165-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed in the preceding owner turn. The focused
assignment tests now pass 16 tests. The assignment `--complete` static check
passed, while the exact `--complete --require-delivery-ready` command failed
with `Preparation acceptance failed: partial/missing packages remain` because
`result.json` truthfully remains partial. See `cpu-static-check.log` and
`cpu-strict-check.log`. These software checks are not delivery proofs. CARLA is
needed only after the CPU package is ready, for actual motion and video review.
No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 saved delivery and comparison checkpoint

`native_capture.py` now compares the loaded Native map name and raw OpenDRIVE
hash against the sealed reviewed site before setting lights or advancing the
world; its planned interval defaults to 900 ticks (45 seconds at 20 Hz).
`lamp_probe.py` rejects a stale source-frame join even if the camera map file
is rehashed. The new `delivery_audit.py` recomputes the exact source-bound
observation from a sealed Native receipt and checks all 900 parked samples,
the requested light-state readback, and four distinct attempt-confined media
files with content hashes. It rejects diagnostic acquisition for delivery and
returns explicit false values for full video decoding, emission/aim review and
physical acceptance. `comparison_audit.audit_saved` processes all three exact
attempts and verifies the reviewed map, parking polygon, blueprint, weather,
camera and controller fixed-condition hashes against actual attempt files.
This is a CPU fixture proof of integrity checks, not a Native recording.

The current exact proof command is
`.venv-cpu/bin/python -m unittest discover -s work/testing__C110454__NRS-484D-165-4__motor_vehicle_driver/tests -v`.
It passed 16 tests; `cpu-lamp-tests.log` is retained. The scoped `--complete`
check passed and scoped `--complete --require-delivery-ready` check failed as
expected for truthful partial status. Logs and hashes are in `result.json`.

Next CPU work: author the exact CARLA owner runner and four original-camera
capture/encoding path, reviewed site packet and physical depressed-aim
construction if supported; complete per-case bundles, finalization, semantic
proposals, offline/compatibility/process-saved proofs, and execution manifest.
Do not infer that low-beam state bits establish emitted intensity or physical
beam aim. `delivery_audit.py` requires later full video decoding and source
inspection before any physical acceptance claim.

## 2026-11-24 original four-camera recorder checkpoint

`camera_recorder.py` now attaches to four caller-owned CARLA camera sensors, requires each callback to match the current Native frame and valid BGRA dimensions, converts those original bytes to lossless PNG, and stores one ZIP archive per view under the attempt directory. Its `finish` method seals each archive with a SHA-256 and exact source-frame count. `native_capture.capture_interval` starts and closes this adapter, includes the four media references in its observational receipt, and releases listeners even when a camera frame drifts. A fake 4-frame Native run reopens and decodes original PNGs; a drifted callback rejects capture before actor-state sources are emitted. These are software tests, not a physical claim about light emission, beam aim or visibility.

The same interface can now supply the `media` references required by the saved delivery integrity auditor after writing the Native receipt. Worker-owned CPU work remains: reviewed site packet and actor-spawn/world-ownership runner, actual depressed-beam-aim alternative if available, canonical semantic proposals, three exact inline bundles, offline/compatibility/process-saved proofs, and full independent source decode/physical review. Keep this assignment partial until the strict gate passes.

## 2026-11-23 three-case diagnostic bundle checkpoint

`build_offline_draft.py` binds the exact unlit, low-beam and high-beam cases to a plan hash, requested light mode, 20-Hz/900-frame capture profile and four original camera views. Each inline construction includes the current Native lamp/camera capture, saved measurement and independent audit code. The bundled runner checks source identity and mode and refuses unsourced Native capture. All three pinned `runtime.py offline` checks passed with materializations under `.runtime-work/`; the 19-test focused suite and pinned preflight passed. These diagnostic bundles are not a canonical execution manifest or original emission/beam-aim evidence.

Proof SHA-256 (logs under this assignment):

- `cpu-lamp-tests.log`: `c06660b0d57e801379e829a38763fc6ee6983f06378e239c147333dbec4cf4a9` (exit 0)
- `cpu-preflight-bundles.log`: `c42488489970abf5debcd8711b4f463f79ab945382f2c8c97e72a78aacfa92f5` (exit 0)
- `cpu-static-check.log`: `718f8cc5dcda62dcf0f81f4249dab89bbeec8a36ef2530dcfb1c01ed938f8e69` (exit 0)
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-unlit.log`: `cdaa8faeff6d6250c565da63f8acd364435904a03465414d36073ee5d5e03203` (exit 0)
- `cpu-offline-low_beam.log`: `bd38bf0af6400083b7400ab1e58b0783dbeb855e006f3b8f8471851c65deb1bb` (exit 0)
- `cpu-offline-high_beam.log`: `6a6d7ee6f402ce96210fad2bf7ed1548fb7e04b7828e26658fd7100742d5179b` (exit 0)

Next CPU work: bind a surveyed Native site/parking actor to a production runner, construct and measure the physical depressed-aim alternative if supported, author canonical proposals and manifest, then source-shaped positive/negative compatibility, saved-only and independent delivery/comparison receipts for every case. Actual emitted intensity, aim, parking and camera visibility remain unverified. Scoped strict fails on truthful `partial` status.
