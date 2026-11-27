# testing__C377875__NRS-484B-460__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.460 — Upon those highways which have official traffic-control devices permitting angle parking, a person shall not stop, stand or park a vehicle other than at the angle to the curb or edge of the highway indicated by such devices.
Assigned branch(es): Device-indicated parking angle.
Cell: C377875 (business_district, angle_park, angle_parking_designation); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C377875__NRS-484B-460__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## November 27 construction and compatibility checkpoint

The immutable `business_district / angle_park / angle_parking_designation` cell fits the sole device-indicated-angle branch of NRS 484B.460. The frozen evidence inventory lists zero accepted recordings and the exact law/actor judgment-range inventory is empty. `case-plan.json` selects six prospective cases: `stop_indicated`, `stop_offset`, `stand_indicated`, `stand_offset`, `park_indicated`, and `park_offset`. Three controlled comparisons hold the original official device, its governed space, highway context, activity class, camera profile and 20 Hz timing fixed while changing the engineering target body-to-curb angle from the indicated 45 degrees to 30 degrees. These requested values are construction probes, not legal cutoffs or observed facts; stop/stand/park classification and device status require original independent review.

`angle_site.py` rejects absent/changed reviewed source packets, non-official or unscoped device claims, invalid highway context, mismatched exact cases and target headings that do not construct the requested geometric contrast. `angle_native.py` and `runner.py` implement lazy CARLA loading, source-sealed map/road and device prop readback, controlled angle approach/hold/depart, 20 Hz body and frame-map capture, four synchronized RGB streams, cleanup and sealed acquisition. `angle_measurement.py` and `analysis.py` bind actual body yaw, curb tangent, official indicated angle and halt frames to original source hashes; fixture provenance remains explicit and no legal verdict is produced. All 15 focused CPU tests pass in `cpu-focused-tests.log`.

`execution-manifest.json` has six primary and six risk-triggered brake-gain fallback constructions. Every exact candidate passed `runtime.py offline`; the corresponding `cpu-offline-<suffix>-<candidate>.log` receipts are bound in the manifest. Every candidate also passed `runtime.py compatibility`, including the selected finalizer, Native-shaped validation, Core conversion and Lean decoder, four source-video decodes, final decode and rejection after `angle-context.json` removal. The exact `compat-<suffix>-<candidate>.json`, `compat-analysis-*.log` and `compat-negative-*.log` receipts are bound in the manifest. Diagnostics are synthetic software fixtures; their reviewed-status fields test source admission only and do not assert original official status, actual positioning, pixels or legal classification. Scoped `worker_check.py --assignment testing__C377875__NRS-484B-460__motor_vehicle_driver --complete` passes in `cpu-scoped-static.log`.

Remaining CPU work is to bind canonical semantic stage proposals and index, source-gated saved-only lifecycle proof, independent physical/delivery and comparison audit scripts with positive and negative fixtures, full manifest acceptance fields, final original-law review and the exact `--require-delivery-ready` gate. Keep `result.json` partial until all pass. Scratch stays under `.runtime-work/c377875-owner/`; set `PYTHONDONTWRITEBYTECODE=1` for every Python command. No CARLA physical or legal result is claimed.
