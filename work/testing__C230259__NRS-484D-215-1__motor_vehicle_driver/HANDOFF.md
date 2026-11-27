# C230259 — NRS 484D.215(1) moving road beams

Status: partial. Exact branch plan and source-bound measurement/construction modules are CPU-tested, but no selected runtime bundle, saved processor, semantic proposals, compatibility receipts, delivery/comparison audit, or strict ready gate exists yet. No original recording or physical beam observation is claimed.

## Frozen scope and evidence

- Law: NRS 484D.215(1), C230259 road/travel/other_vehicle, motor_vehicle_driver, full-test.
- Frozen accepted inventory: zero recordings. No original Native frame, calibrated light source, or reviewed physical beam pixels are supplied. `case-plan.json.evidence_review` records the source-backed gap.
- The exact law conditions operation on the traveled highway or adjacent shoulder during NRS 484D.100 times. It requires a distribution that reveals persons and vehicles a safe distance ahead. An oncoming approach within 500 feet adds the glare condition. The lowermost distribution specified by NRS 484D.210(2) is deemed to avoid glare regardless of contour and loading. Neither a numeric safe-distance threshold nor a calibrated glare cutoff is supplied.
- `inputs/testing__C230259__NRS-484D-215-1__motor_vehicle_driver/judgment_ranges.json` has no entry for this exact law and actor. The 500-foot statutory boundary remains a distinct measured condition.

## Exact cases and comparisons

`case-plan.json` now has 8 selected delivery cases: `general_high`, `general_low`, `general_dark`, `oncoming_499_high`, `oncoming_499_low`, `oncoming_500_low`, `oncoming_501_low`, and `oncoming_499_low_crest_loaded`, each prefixed with the assignment ID. Six controlled comparisons cover general beam distribution, no distribution, near-oncoming high versus low, 499/500 and 500/501 feet, and low beam at level/standard versus crest/loaded. The requested initial distances are engineering targets; original frame-by-frame body and eye separations determine physical exposure. The contour/load contrast is explicit, and no requested beam mode is treated as proof of the statutory lowermost distribution.

## CPU implementation and proof

- `build_case_plan.py` derives every exact case, requirement disposition, comparison and source gap from the frozen assignment.
- `beam_construction.py` rejects changed source hashes, wrong identities, missing person/vehicle targets, unreviewed geometry, nonopposing routes, wrong 500-foot request, missing motor vehicle blueprints, eye offsets, positive speed requests, and incomplete four-camera poses. Its injected adapter creates both moving vehicles, both targets, routes, requested beam state and four cameras.
- `beam_measure.py` validates hash-sealed site/actor/camera sources, 900 original synchronized 20 Hz frames, stable IDs and all participant observations. It reports original body and eye separations, the 152.4 m threshold predicate, target distances and lamp command/readback while retaining unresolved physical and legal judgments.
- `beam_camera.py` archives synchronized original PNG frames and encodes four lossless FFV1 streams; it is adapted from the already CPU-tested C110454 original camera recorder.
- `beam_pixels.py` independently reads original person, vehicle and oncoming-eye camera pixels from hash-sealed ZIPs and frame-specific reviewed projection ROIs. It reports 8-bit RGB luma without claiming calibrated light intensity or legal glare.
- `beam_projection.py` projects original Native body and driver-eye geometry through the actual camera inverse matrix and FOV; behind-camera and invalid calibration inputs are rejected.
- `beam_native.py` implements a lazy CARLA operator that verifies the reviewed map, owns world settings and actors, records source frame joins, original actor/beam observations, frame-specific ROIs and four cameras, and restores settings. It has not yet been exercised by a source-shaped fake operator test or physical CARLA. Physical packet refinement, full finalization and runtime bundle binding remain CPU work.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C230259__NRS-484D-215-1__motor_vehicle_driver -p 'test_*.py' -v` passes 21 tests; log `cpu-beam-tests.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C230259__NRS-484D-215-1__motor_vehicle_driver --complete` passed static partial validation after the case-plan update. It does not establish delivery readiness.

## Exact next CPU work

1. Repair and fake-test `beam_native.py` including full source packet closure, road footprint and cleanup on partial sensor failure; connect runner/config/construction and case-specific source hashes.
2. Finalize Native result and 900-frame video/trace map, saved-only measurement analysis and physical completion. Validate actual pixel review inputs separately from API light bits.
3. Build measurement contracts, source-hashed diagnostic recipes, offline and positive/negative compatibility proofs for each exact case and any justified risk fallback.
4. Add all canonical semantic proposals, source-bound delivery and controlled comparison audits with negative tests, post-capture manifests and queue proposal.
5. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230259__NRS-484D-215-1__motor_vehicle_driver --complete --require-delivery-ready`; repair any failure before marking ready.

Physical CARLA motion, actual illumination, eye glare, camera visibility and statutory interpretation require later independent original-source review and are not established by CPU fixtures.
