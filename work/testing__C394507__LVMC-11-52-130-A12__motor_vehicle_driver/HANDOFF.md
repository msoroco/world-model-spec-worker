# testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No original physical recording or legal conclusion is claimed.

LVMC 11.52.130(A)(12) concerns stopping, standing or parking a vehicle within twenty feet of a marked crosswalk, subject to the text's traffic-conflict, legal-compliance and officer/device-direction exceptions. The C394507 destination-stop witness is conditional. Frozen accepted evidence contains zero exact-assignment recordings and zero exact-law judgment-range entries.

## Constructed CPU work

`case-plan.json` defines nine unexecuted cases and eight controlled comparisons. They separate body clearance targets 5.9, 6.096 and 6.3 m; stop, stand and park activities; necessary traffic-conflict avoidance; police and device directions; and a crossing without markings. These are construction targets, not legal conclusions. Original source requests include jurisdiction, driver/person and vehicle identity, destination purpose, actual service activity, crossing markings, traffic and applicable directions.

`crosswalk_clearance.py` consumes a hash-sealed original Native context and 20 Hz body polygon/speed trace. It checks exact source identity and frame cadence, requires marked-crosswalk extent and exception-context sources, computes full-body polygon clearance from the marked crosswalk, and retains 6.096 m solely as the twenty-foot arithmetic reference. It leaves legal distance convention, exact boundary treatment, stop/stand/park classification and exception judgment unresolved. Seven focused tests cover clearance, overlap/containment, plan controls and rejection of changed, diagnostic or incomplete sources.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver/tests -v`: exit 0; `cpu-crosswalk-tests.log` SHA256 `5613599727057f3ccf56fa0e8bb961b7a3153ca8593d21d192275008a0af1c11`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `26c401fa5cee336cdd153698981c5501a448193258a3a65c27ca81c6c0630ee2`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build and prove exact Native scene/controller, original full-duration 20 Hz four-camera capture, source-bound finalizer and semantic proposal, saved compatibility/processing, and delivery/comparison audits. Resolve the legal measurement convention and exact boundary treatment from authoritative supplied sources before classification. Actual CARLA motion, crosswalk markings and camera visibility remain physical checks after CPU preparation. No missing-tool or dependency blocker is asserted.
