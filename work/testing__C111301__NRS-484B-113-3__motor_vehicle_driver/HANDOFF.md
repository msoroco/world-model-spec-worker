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

## 2026-11-24 saved-only source join checkpoint

`saved_backing.py` now accepts only the two exact case IDs and a declared non-diagnostic Native original acquisition. It verifies the SHA-256 and confined path of the original map packet, 900 telemetry rows, 900 original frame-map rows, and four named media files. It checks contiguous original frame identities, 20 Hz time steps, four camera frame readbacks per tick, and measured backing plus a moving pedestrian in the backing corridor. It outputs a source-bound measurement and explicitly leaves video decode, pixels, physical completion, and legal judgment unresolved. The media fixture is textual and proves only hash joining.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 13 tests, including source tamper, missing media, camera frame drift, time gap, diagnostic source, identity mismatch, and path escape rejection. See `cpu-backing-tests.log` and its result.json hash.

Remaining CPU work: connect this saved join to original Native capture and finalizer, validate full media pixels with the runtime auditor, implement independent delivery/comparison audits and canonical bundles/proposals/receipts. The selected C111301 map source and physical vehicle/pedestrian interaction still need local verification.

## 2026-11-24 replayable saved comparison checkpoint

`saved_comparison.py` now runs the exact `pedestrian_yield_response` comparison from two distinct sealed original Native acquisitions. It invokes `saved_backing.process` for each required case, checks that the two original map packets have the same hash (binding map, routes, blueprints and control context), requires the same 900-tick time window, and calls `backing_measurements.compare` to check measured pedestrian exposure and an observed brake or reverse-speed difference. The CLI emits a compact source-hashed comparison receipt only after both attempts pass. It leaves physical completion and legal judgment unresolved.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 16 tests. These include a positive CLI replay and rejection of changed source context, telemetry tampering and pedestrian-exposure drift. `.venv-cpu/bin/python runtime.py preflight` passed with the pinned CPU environment and Lean toolchain. The logs and current hashes are in `result.json`.

Next CPU work: attach original four-camera capture and full media decode, then implement the exact delivery auditor, canonical case bundles, proposals and source-specific offline/compatibility receipts. The selected C111301 site and realized interaction remain unverified. This package remains partial; synthetic sealed fixtures are software tests only.
