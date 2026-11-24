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

## 2026-11-23 original camera profile enforcement

`camera_recorder.py` now requires each original callback to match the declared 1920×1080 overview or 1280×720 detail-view dimensions before encoding. The diagnostic bundle config and runner preflight bind these dimensions, and a new fake-Native negative test confirms that a mismatched frame is rejected before actor-state sources are emitted and all listeners are stopped. The three inline constructions were regenerated to carry current code. This is a software source-shape check, not proof of actual lamp emission, aim or image visibility.

Pinned preflight, bundle build, all **20** focused tests, three exact offline construction checks and scoped static exited 0. The exact scoped strict gate exited 1 because status remains partial. The commands and cleaned SHA-256 logs are in `result.json.tests`. Next CPU work remains a reviewed intersection site and production owner runner, physical aim branch if supported, canonical proposals/manifest and exact compatibility, saved-only and delivery audit receipts.

## 2026-11-23 original camera decode checkpoint

`delivery_audit.py` now opens each nondiagnostic camera ZIP and fully decodes its PNGs. It requires the exact Native frame names and source-frame map, no duplicate or missing ZIP entries, and the pinned overview/detail dimensions. A small original-shaped two-frame fixture verifies four positive archives and rejects a changed frame map or dimensions; text-only diagnostic stand-ins still do not claim decode. The delivery receipt reports full decode only after the nondiagnostic 900-frame path passes. This checks saved pixels and timing identity, not visible beam emission, physical aim or legal parking.

The three exact diagnostic constructions were rebuilt with this code and all three offline checks pass. Twenty-one focused tests, pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial status. Eight new SHA-bound logs are recorded in `result.json`. Reviewed Native site, production owner runner, physical aim branch, canonical proposals/manifest, positive-negative compatibility and saved-only delivery receipts remain CPU work.

## 2026-11-23 exact headlamp semantic proposals

`build_semantic_proposals.py` binds the frozen NRS 484D.165(4) text, assignment, case plan and all three exact diagnostic construction hashes into draft relevance, template, bindings, cases and semantic-index stages. The unlit/low/high proposals vary only requested mode; the two comparisons preserve the frozen fixed conditions. Actual parked status, lamp illumination and emitted beam depression/dimming remain independently unresolved; API bits are not a legal outcome. Four new tests reject quote, case and comparison drift.

Twenty-five focused tests, pinned preflight, all three exact offline diagnostics and scoped static pass. Exact scoped strict exits 1 on truthful partial. Reviewed original site, beam-aim source, production runner, canonical manifest, positive/negative compatibility and saved delivery remain CPU work.

- `cpu-semantic-build.log` SHA256 `b2d9e0c23f1407d0771771fad186dc28aed0b3c85b831fa527a2c14e735e638d`; exit 0.
- `cpu-semantic-tests.log` SHA256 `90f45f3ca2e21c268211f24baa83db4a2cd4c04cb414da8e7293613877471558`; exit 0.
- `cpu-semantic-preflight.log` SHA256 `ca3e5c4252ec2838ce31a5d9991a7b5df8331688503f333bed640769fa0d03f2`; exit 0.
- `cpu-semantic-static.log` SHA256 `718f8cc5dcda62dcf0f81f4249dab89bbeec8a36ef2530dcfb1c01ed938f8e69`; exit 0.
- `cpu-semantic-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; exit 1.
- `cpu-semantic-offline-unlit.log` SHA256 `ddf31674966111b00ff71780f0921fc32d9ce96a273eb8a3556efb80f05b0bc2`; exit 0.
- `cpu-semantic-offline-low_beam.log` SHA256 `f7a5b54cfdf4613f92c9001e1cfff3247ffa9f6d7993149caef4ed39a7d5ba30`; exit 0.
- `cpu-semantic-offline-high_beam.log` SHA256 `17ebcf13c266e3efd850945a1a98cfa3537c0ac5816b5554364c7133983de5d2`; exit 0.

## 2026-11-24 operator-owned parked-headlamp Native entrypoint

`owned_capture.py` SHA256 `1e4203c032de0c9c850d8c5faf0ace5b77340bf03e71b2894c653b5e12d0c533` now source-gates an exact parked-headlamp site packet against the loaded OpenDRIVE, spawns a parked vehicle and the four pinned RGB camera views, invokes the original `capture_interval`, writes its Native receipt, destroys owned actors and restores the operator world after both success and failure. The packet must name separate parking and intersection source references; those references still require independent source review. The three inline bundles now contain this wrapper and a lazy CARLA runner that validates packet case/provenance before opening a client.

The focused suite passes 27 tests (`cpu-owned-tests.log` SHA256 `54d19c95d624ecc47238243487fcc545764693651f22a224df6955a0a7086d61`), including fake-world success/failure lifecycle and mocked bundle entrypoint checks. All three rebuilt exact bundles pass pinned offline. Pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Commands and hash-bound logs are in `result.json`. Original emitted light, beam depression/dimming, public-site authority and actual pixels remain unverified. Next CPU work: review original site and beam sources, then produce positive/negative compatibility, saved processing, canonical manifest and independent delivery receipts.

## 2026-11-24 sealed acquisition finalizer checkpoint

`acquisition_finalizer.py` now reads `native-source-receipt.json` from the exact attempt, requires its case/mode and 900-frame duration, and checks all four original camera path and SHA-256 seals before constructing `acquisition.json`. It invokes the existing saved delivery auditor and removes the new manifest if source or audit validation fails. Diagnostic fixtures require explicit `allow_diagnostic=True`; they cannot pass as Native production acquisitions. The finalizer is embedded in all three exact diagnostic bundles. Neither it nor the fixture establishes emitted brightness, physical beam depression/dimming or legal parking.

Proof: 30 focused tests, pinned preflight, three rebuilt exact offline checks and scoped static pass. Exact scoped strict exits 1 on truthful partial. SHA-bound commands and logs are in `result.json` under `cpu-acquisition-*`. Reviewed original site/beam sources, canonical manifest, positive/negative compatibility and true Native saved-delivery receipts remain CPU work; physical emission and aim require later review.

## 2026-11-24 original lamp-region pixel checkpoint

`lamp_photometry.py` now measures original RGB pixels from a sealed camera ZIP using source-hashed fixed lamp and background polygons. It checks the reviewed ROI source identity, frame-by-frame Native camera join, original ZIP inventory and image dimensions, then reports per-frame lamp minus background pixel luma. A controlled comparison requires identical ROI and frame identities and distinct original media. Its output does not equate 8-bit pixel brightness to emitted intensity or physical beam depression/dimming, and no legal result is inferred. The ROI in CPU tests is explicitly a fixture; a reviewed Native site and actual ROI source are still needed.

The module is embedded in all three exact diagnostic constructions. Thirty-three focused tests, pinned preflight, three exact offline checks and scoped static passed. The exact scoped strict gate exited 1 on truthful `partial`. Next CPU work is source-reviewed site and ROI integration, real beam-aim capability investigation, canonical manifest and positive/negative compatibility/process-saved and complete delivery/comparison receipts.

SHA-256 source and proof index:

- `lamp_photometry.py`: `89ba68213ef2c55e36b72c9d7b074efcf82b7f1fa25391be985ab66e39796482`
- `tests/test_lamp_photometry.py`: `20d5225cd3b46b720de6e5d481b56491957ae53000bc518293f731a5359870ac`
- `build_offline_draft.py`: `47e605ce43717782d909d0feebc587afccc791ff0018fb50b9464ba25d869b8a`
- `execution-manifest.draft.json`: `4334d451fdfbdfc239f3221219b11e6c482060966964cf67264859d46588fa8a`
- `construction-unlit.json`: `1c234a0963eedcf64212274be3ebd9e3dd12cf8addd00716c3ba12731dcb7742`
- `construction-low_beam.json`: `03037c6a78fd77582f009d0c7cf946250443ff64006c4fc510e72449ddc2b8ce`
- `construction-high_beam.json`: `eb0a65b30e2281095d765331ba443924563d97076346663c859774e49473975e`
- `cpu-photometry-build.log`: `00beba5ec219a22edc73458ecda127ad8537ac3a73791c9b7da7808559b2b82b`
- `cpu-photometry-tests.log`: `d7e93a8c597dd666c9192bd8ee2d93f55e76e40716d323926363885137ed9566`
- `cpu-photometry-preflight.log`: `c6b3c06ef7d65e81bdf7ee6a658d5d1c74d1c2b96ac706a60d0089e5e7f91e14`
- `cpu-photometry-offline-unlit.log`: `fbfd87b1059d391f2d7ea4b07bc789445699a46d73855ae1cca319e72fe36189`
- `cpu-photometry-offline-low_beam.log`: `6134f2f79b3e8ec8b47bd71db4a89f7005d20812a7e6133f0df9ce0f3de87b14`
- `cpu-photometry-offline-high_beam.log`: `fcd6bcee56ed9dd52080464c4ef851e614e05c6b6fe0b235caff1d462100c4f8`
- `cpu-photometry-static.log`: `718f8cc5dcda62dcf0f81f4249dab89bbeec8a36ef2530dcfb1c01ed938f8e69`
- `cpu-photometry-strict.log`: `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`
