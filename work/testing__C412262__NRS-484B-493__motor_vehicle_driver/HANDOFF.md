# testing__C412262__NRS-484B-493__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No original physical recording or legal conclusion is claimed.

NRS 484B.493 concerns standing or parking on the left-hand side of a one-way street when official traffic-control devices are erected giving notice. The C412262 witness targets left-side parking. Frozen accepted evidence contains zero exact-assignment recordings and zero exact-law judgment-range entries.

## Constructed CPU work

`case-plan.json` defines nine unexecuted exact variants and eight controlled comparisons. It isolates parking, standing, travel and temporary halt; left versus right side and reversal of the permitted direction; one-way versus two-way status; and erected applicable, absent and out-of-extent notice. Each requests source-backed street legal status and boundaries, one-way order, device erection/authority/content/conformity/extent, responsible person and vehicle, purpose and service activity, original 20 Hz body trace and four cameras.

`one_way_side_observations.py` consumes hash-sealed original Native context/receipt and 20 Hz vehicle center/body polygon trace. It validates exact identity, source hashes, permitted-direction centerline and cadence; then measures signed left offsets for the center and entire body relative to that centerline. Offset sign changes when permitted direction reverses. It does not invent a legal left-hand-side cutoff or infer standing, parking or notice applicability. Seven focused tests cover positive/reversed geometry and rejection of diagnostic, changed, notice-incomplete or degenerate sources.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C412262__NRS-484B-493__motor_vehicle_driver/tests -v`: exit 0; `cpu-side-tests.log` SHA256 `4bbd63a9c93d8b42ccc3067efbf936ee5a2128b9c80aae50f0785b4f639fd41d`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C412262__NRS-484B-493__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `9c19e4f2f99580e0cef7abf917ffef64c9b7f5c6e4abe9a2cdece2a0f3082e03`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C412262__NRS-484B-493__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build/prove the exact Native street/device scene and parking controller, full original 20 Hz four-camera capture, source-bound finalizer and semantic proposal, saved compatibility/processing, and delivery/comparison audits. Resolve statutory side and standing/parking classification from supplied sources, including actual device notice and extent. Actual CARLA motion, one-way geometry, signs and cameras remain physical checks after CPU preparation. No missing-tool or dependency blocker is asserted.
