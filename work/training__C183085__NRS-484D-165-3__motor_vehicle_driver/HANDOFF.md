# NRS-484D-165-3 at C183085

Actor: `motor_vehicle_driver`. Frozen cell: `paved_shoulder` / `stop_stand` / `other_vehicle`.

Exact statutory source: NRS 484D.165(3); with 484D.165(1). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Stopped vehicle on adjacent paved shoulder. Planned comparison variable: `parked_lamp_display`. Requests: stopped vehicle displays required front and rear lamps in low light; stopped vehicle omits required displayed lamps in low light. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the vehicle is parked or stopped on the travelled portion of a highway or the adjacent shoulder; the time is within the lighting section's hours; there is insufficient light to reveal a person or object at 1,000 feet.

Timing to retain: the lamps must be displayed for the whole time the vehicle stands under those conditions; the hours come from the lighting section, so the same clock condition applies.

Exceptions and numeric alternatives planned: ambient reveal distance numeric boundary 1000 feet; front lamp visibility numeric boundary 500 feet; rear lamp visibility numeric boundary 500 feet.

Unresolved judgment or rule composition: the lamps' visibility distances (500 feet front and rear) are equipment properties, not observations of the scene; what a source sees is whether a lamp of that colour is lit and on which side. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU lamp and distance source diagnostic

Added `native/shoulder_lamp_measure.py` and `native/prove_shoulder_lamp_measure.py`. The saved-source diagnostic requires lighting-hours and adjacent-shoulder source statements, 600 joined frames at 20 Hz, four pinned camera identities, continuous stopped speed, front white/amber and rear red lamp status on every frame, and the lamp side closest to passing traffic. It reports per-frame lamp omissions. It retains separate estimated distance and uncertainty brackets for ambient reveal (1,000 feet) and front/rear visibility (500 feet), returning below/above/overlaps rather than collapsing a boundary interval to a legal verdict. The 0.05 m/s stop check is only an engineering sampling diagnostic.

The proof builds all eleven planned source shapes under `.runtime-work/`: two lamp-display witnesses and nine numeric bracket examples at 990/1000/1010 and 495/500/505 feet. All use 600 synthetic frames, no Native pixels or calibrated optical measurement. Six missing-source mutations reject lighting hours, shoulder location, ambient probe, interval truncation, a camera, and a lamp status. These fixture values do not establish actual visibility or equipment compliance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_shoulder_lamp_measure.py > native/shoulder-lamp-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C183085__NRS-484D-165-3__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `aa349fb4dae605823562f1baa212c3251020e77883df7aa821c43c37aaf0175d`; proof script `1cb7e0237921cbd814116df3782b4fba8b98c781d703c74729046d128f83c3b4`; proof result `b3d679b097d67a25078e642cda01ce094a450cb1f8bb7295418dd5c29ea91164`; preflight log `519a1fdc5a6cdb51ca7e2342f97830dfdd63d1c3fe396a47e08a06acfe7de23c`; scoped checkpoint log `059a081576ea58029ded7d014920c53732c634b11ea786bbcd37a20dfb25c658`.

Next CPU work: construct the exact paved-shoulder Native scene, timed lamp controller and near-traffic-side placement, four camera streams, and a calibrated source method for ambient and front/rear optical probes. Bind eleven selected cases to an execution manifest and run pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. There is no exact construction bundle yet, so those proofs remain undone. Keep the assignment partial.

## 2026-11-27 selected Native construction checkpoint

Added `native/selected_runner.py`, `native/selected_offline_test.py`, and `native/build_selected.py`. The generated `selected-shoulder-draft-manifest.json` binds 11 exact case constructions under `native/selected-*-construction.json`: witness_1, witness_2 and numeric_1/2/3 below, at and above. Each materializes a 600-frame, 20 Hz, four-camera runner. The runner requires an original map, shoulder, passing-lane, civil-time, lighting-hours and optical-protocol survey; it verifies the surveyed pose is on a mapped shoulder, places a distinct passing-traffic reference vehicle, applies full-interval stopped control and lamp commands, records source lamp bits and synchronized camera/frame identities, and restores the world. Camera pixels and command bits are source material for later review, not proof of emitted lamp color, 500-foot optical visibility or 1,000-foot ambient reveal. The numeric requested values remain targets, not measurements.

All 11 exact `.venv-cpu/bin/python runtime.py offline --manifest work/training__C183085__NRS-484D-165-3__motor_vehicle_driver/selected-shoulder-draft-manifest.json --case CASE --output .runtime-work/c183085-offline/v2-SUFFIX` checks passed (exit 0). Logs: `native/selected-SUFFIX-offline.log`. Final manifest SHA-256: `c201cd4055791036b7bfa569a369aaef3a92cc5054eee5e3760421e174fdde41`; runner SHA-256: `824d7910920b0596f46be2dc7eac753e86dfcbebeb2139f78710c947bf32e5d3`. Output and TMPDIR were under `.runtime-work/`; bytecode was disabled.

Remaining CPU work: connect the existing source diagnostic to exact saved Native frame maps, camera video, Core capture, per-case selected-requirement measurement contracts and canonical result writing. Build source-hashed fixture recipes and exact positive/negative compatibility and process-saved receipts; add canonical semantic proposals and independent physical/lifecycle, delivery and comparison audits. Calibrated original optical measurement protocols and observations are not present in the exported sources; preserve that limitation and keep numeric results unknown until original local evidence exists. Reassess the physical shoulder and passing-lane geometry during local Native execution. The scoped strict ready gate has not passed.
