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
