# testing__C229404__NRS-484B-477-2__motor_vehicle_driver

Status: partial CPU preparation. The scoped strict delivery gate exits 1 because this result remains partial. No original accepted recording exists in the frozen evidence inventory; none is claimed.

## Exact coverage

NRS 484B.477(2) prohibits stopping, standing or parking a vehicle within a qualifying alley in a position that blocks a driveway or entrance to abutting property. C229404 fixes road/park/driveway_entrance and motor_vehicle_driver. The conditional witness requires independent proof that the connected road qualifies as an alley, is a highway and is not a cul-de-sac; that the property abuts it; and that the driveway or entrance serves permitted vehicular use. No numeric statutory blocking cutoff appears. The exact law has no judgment-range entry for this actor.

`case-plan.json` has four planned exact cases: `testing__C229404__NRS-484B-477-2__motor_vehicle_driver__driveway_clear`, `testing__C229404__NRS-484B-477-2__motor_vehicle_driver__driveway_overlap`, `testing__C229404__NRS-484B-477-2__motor_vehicle_driver__entrance_clear`, and `testing__C229404__NRS-484B-477-2__motor_vehicle_driver__entrance_overlap`. The two within-access-kind comparisons fix alley/parcel/vehicle/access geometry and vary parking target. These are planned test positions, not legal outcome labels. Each case maps to the one missing-original-evidence gap; frozen accepted evidence contains zero recordings. Stopping, standing and parking phases are measured within the parking episode; no exception is imported from another statute.

## Implemented CPU work

- `access_measurement.py` loads SHA-256-bound original Native frame map, alley geometry, vehicle footprint, and activity packets. It requires 900 consecutive 20 Hz frames, complete per-frame joins, qualifying-alley and abutting-access provenance, actual parked phase, and convex body/access polygons. It computes original per-halt-frame access intersection area. Statutory blocking remains unresolved.
- `comparison_audit.py` independently remeasures both attempts, checks fixed original alley/property/access fields and duration, and requires the deliberate footprint position difference to appear in the measurements.
- `measurement-contract.json` lists exact source and output obligations. `tests/test_access_measurement.py` exercises overlap and clearance, both access kinds, stale/missing source rejection, nonqualifying alley and missing abutting provenance rejection, and changed-comparison-geometry rejection. Fixtures are synthetic software checks only.

## Proof receipts

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA-256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C229404__NRS-484B-477-2__motor_vehicle_driver/tests -v`: exit 0; `cpu-access-tests.log` SHA-256 `1f002e66ef57d467e473b45ca0e7ebc3972d773f37480bf3070ea00128d80eb9`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229404__NRS-484B-477-2__motor_vehicle_driver --complete`: exit 0; `cpu-static-check.log` SHA-256 `889b7e0aa9d5d7629bed94f73abfad95cb86d301a8f9adf4acd5b2bbd59bd893`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C229404__NRS-484B-477-2__motor_vehicle_driver --complete --require-delivery-ready`: exit 1; `cpu-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

## Remaining CPU construction

Implement all four CARLA constructions and controllers with a connected qualifying alley and actual driveway/entrance access, original capture packet acquisition, case-specific saved finalizers, four-camera configuration, semantic proposals, offline and positive/negative compatibility receipts, independent delivery audits, comparison command receipts and manifest risk/fallback proofs. Then rerun the exact scoped strict gate. Current `candidate_risk` entries flag map/collision placement risk but do not yet supply validated fallbacks. Physical motion, visual coverage and legal blocking review are later original-capture checks; they do not replace the remaining CPU work.

## Native acquisition and saved-source audit checkpoint

`native_capture.py` now provides an injected Native adapter path for every exact driveway/entrance clear/overlap case. It seals the original OpenDRIVE hash and access-provenance packet before motion, requires 900 consecutive 20 Hz frame joins, original ego polygons/activity and four synchronized camera archives, then rechecks map bytes after motion. It writes immutable source hashes and calls `access_measurement.measure`; a diagnostic adapter remains explicitly marked as a fixture. `delivery_audit.py` independently rejects diagnostic fixtures for original delivery, stale map/camera bytes and incomplete media joins. It reports engineering intrusion only and leaves statutory blocking unresolved. The eleven focused tests include successful fake-adapter acquisition for all four cases and negative map/camera mutation checks. The fake adapter is software diagnostic evidence, not an accepted recording or a substitute for a connected qualifying alley survey.

Remaining CPU work: author the actual connected-alley OpenDRIVE and driveway/entrance geometry, CARLA adapter and parking controller, production camera setup and full media decode, source-hashed exact case diagnostics, positive/negative compatibility, semantic proposals, per-case execution manifest and fallback receipts, saved-only finalizer integration and delivery/comparison command receipts. The construction must establish highway/alley/not-cul-de-sac, abutting parcel ownership and permitted vehicular use with original independent sources rather than map labels. Original physical motion, visibility and legal blocking judgment stay pending after CPU preparation.

`alley_construction.py` computes source-surveyed clear/overlap parking targets along a connected alley centerline with the same controller and capture settings in each comparison. Both approach directions and missing connected-end provenance are CPU-tested. It requires original endpoint sources and vehicle dimensions; the 2 m clear target margin is an engineering setup choice, not a statutory blocking threshold. The injected adapter receives this exact plan but realized parking position still comes solely from saved original frame measurements.

`parking_controller.py` now supplies a low-level route-tracking, braking, minimum-20-second hold and departure state machine for the adapter plan. It uses Native pose and speed readback, rejects leaving the surveyed route, and never claims a target was realized merely because control was requested. CPU tests exercise both approach directions and the stop/hold/depart transitions. The production CARLA adapter still needs to invoke it and report measured state.

The camera inventory now uses the exported prospective profile names `overview`, `approach`, `reference_corner`, `driver_reference`. The saved audit fully decodes all 900 PNGs from each camera and, for original delivery, checks 1920x1080 overview and 1280x720 detail dimensions. Diagnostic fixtures remain explicitly excluded from original-delivery claims. This still does not prove physical camera coverage or local acceptance.
