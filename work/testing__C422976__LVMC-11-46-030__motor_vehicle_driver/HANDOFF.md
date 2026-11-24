# testing__C422976__LVMC-11-46-030__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No original physical recording or legal conclusion is claimed.

LVMC 11.46.030 concerns a stop not less than fifty feet from the nearest side of a school pedestrian lane while a stationed person or device warns that children are about to cross or crossing, then waiting for a stated release alternative. The C422976 witness targets a human warning followed by an observed go signal, continued presence or departure. Frozen accepted evidence contains zero exact-assignment recordings and zero exact-law judgment-range entries.

## Constructed CPU work

`case-plan.json` defines nine unexecuted exact variants and eight controlled comparisons. It isolates 49, 50 and 51-foot construction targets; human go signal, continued warning, person departure and premature proceeding; a raised device signal; no warning; and person presence without child-crossing warning. It requests source-backed lane nearest-side geometry, jurisdiction, warning and release sources, actual children status, vehicle motion and four cameras. Construction targets do not decide legal boundary treatment.

`school_lane_observations.py` consumes hash-sealed original Native context/receipt and 20 Hz ego speed/reference-station trace. It requires original school pedestrian-lane nearest-side and vehicle reference-point sources, stationed human warning, child status, go signal, locality/departure and device release annotations. It measures reference-to-nearest-side distance in feet and exact zero-speed samples. It leaves the legal measurement convention, locality boundary, fifty-foot stop determination and release/proceed judgment unresolved. Seven focused tests cover distance, cessation and rejection of diagnostic, changed or incomplete sources.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C422976__LVMC-11-46-030__motor_vehicle_driver/tests -v`: exit 0; `cpu-school-tests.log` SHA256 `860214c0ff9bcd45272e3781fc51703111503c11f85b37f2cb21a31d77585f7a`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C422976__LVMC-11-46-030__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `97cf1a1a4dd97d04c6ea75286322c507b1bffa57bb2691f90ec304336ed73fa5`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C422976__LVMC-11-46-030__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build/prove the exact Native school-lane scene/controller, full original 20 Hz four-camera capture, source-bound finalizer and semantic proposal, saved compatibility/processing, and delivery/comparison audits. Resolve legal vehicle reference point, nearest-side measurement and locality boundary from supplied sources before classification. Actual CARLA human signals, children, lane geometry and cameras remain physical checks after CPU preparation. No missing-tool or dependency blocker is asserted.
