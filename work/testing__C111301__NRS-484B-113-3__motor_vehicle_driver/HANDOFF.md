# testing__C111301__NRS-484B-113-3__motor_vehicle_driver

Status: partial CPU construction checkpoint. The exact strict gate still fails because result.json is partial. No Native recording or accepted evidence is claimed.

The frozen cell is C111301 (intersection, travel, pedestrian control), with motor vehicle driver. The assigned witness is the pedestrian alternative of NRS 484B.113(3). The full subsection also says moving traffic; that alternative needs independent branch allocation review. The section heading is limitations on backing. A travel label or pedestrian control does not by itself prove backing, a crosswalk, or legal right of way. Frozen evidence.json lists no accepted recordings, and judgment_ranges.json has no matching range for this law and actor.

## Exact cases and comparison

- `testing__C111301__NRS-484B-113-3__motor_vehicle_driver__pedestrian_yield`: reverse vehicle holds/brakes while a distinct moving pedestrian occupies the backing corridor, then resumes after clearance.
- `testing__C111301__NRS-484B-113-3__motor_vehicle_driver__pedestrian_continue`: same map, actor classes, reverse and walking routes, and pedestrian exposure; driver continues backing.
- `pedestrian_yield_response`: compare measured original-frame brake/reverse speed with measured pedestrian gap, speed and corridor occupancy held fixed. This is an engineering contrast, not a legal label.

`backing_geometry.py` requires an original source-hashed map/junction packet, vehicle and pedestrian blueprints, route coordinates and references, control provenance, and a geometric route intersection. It rejects a pedestrian path missing the reverse body corridor. `native_backing.py` lazily resolves native blueprints and spawns both actors with cleanup on failure. `backing_controller.py` injects a control factory for Native VehicleControl and commands hold/release or continued reverse. `backing_measurements.py` rejects missing original frame fields, identity changes, absent measured backing, absent moving pedestrian conflict, and comparison exposure drift.

## Proven checks

- `.venv-cpu/bin/python runtime.py preflight` passed in this turn.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 7 tests. Exact log and SHA are in result.json.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111301__NRS-484B-113-3__motor_vehicle_driver --complete --require-delivery-ready` reached `Preparation acceptance failed: partial/missing packages remain`; see strict-gate.log. It is deliberately not marked ready.

## Next CPU work

1. Select and review an actual CARLA/OpenDRIVE C111301 site, export its original map packet and Native transforms, and bind reverse motion to the validated path. Do not infer physical geometry from the cell label.
2. Integrate the controller and original-frame measurements into canonical runner/config/construction and exact bundled case variants. Preserve four-view 20 Hz capture and original telemetry.
3. Author canonical semantic proposals, exact measurement contracts, source-specific positive/negative compatibility recipes and offline receipts for each case, plus saved-only processor and independent delivery/comparison audits.
4. Re-read the full statutory subsection and definitions for the moving-traffic alternative and section-context limits. Keep all legal judgments unresolved pending physical review.
5. Rerun the seven CPU tests and exact strict gate. Mark ready only after the gate passes.

Actual CARLA motion and camera visibility remain later GPU checks; the listed package work is worker-owned CPU preparation. No external blocker is asserted.
