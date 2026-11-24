# testing__C125763__NRS-484B-250-1__motor_vehicle_driver

Status: partial exact-pair source-bound measurement. Two prior accepted case IDs are retained for original-source review; no new recording or physical acceptance is claimed.

Exact law: NRS 484B.250(1); with 484B.250(5) — The driver of a vehicle approaching an intersection shall yield the right-of-way to a vehicle which has entered the intersection from a different highway. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Other vehicle enters the same statutory roadway crossing at a median opening before ego..
Cell: C125763 (median_opening, travel, yield_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU implementation and evidence limits

- `saved_crossing.py` requires SHA256-bound original `road.xodr`, `site-context.json`, ego and other Native body histories. It checks reviewed map identity, different highway identities, the fixed C125763 yield sign, explicit device governance and subsection-4 review status, distinct actor IDs, contiguous joined 20 Hz frames, convex footprints and crossing geometry, both body entries and exits, and simultaneous occupancy. It retains original transition brackets, reports other-first and clearance order, and issues no legal finding.
- Its pair audit holds crossing, roadway, other-vehicle entry/exit, yield-sign governance, subsection-4 status, approaches and frame count fixed while checking a measured ego clearance-order change. Tests reject missing/stale sources, incomplete histories, bad joins, changed governance and wrong highway relations.
- `native_crossing.py` samples both actors' original world-space footprints on one Native tick and supplies bounded hold/route-follow control. Routes and construction remain to be bound to a reviewed live map and tested in CARLA.
- `case-plan.json` lists exact `__precedence` and `__advance` cases, their frozen accepted IDs and `official_yield_precedence` comparison. Frozen metadata reports accepted 1,100-frame recordings, but original video, trace, site map and local audit bytes are absent from this export. Metadata cannot prove physical entry order or comparison isolation. Because this cell's fixed control is `yield_sign`, the subsection-5 official-device exception and unresolved subsection-4 qualification remain explicit.

## Next CPU actions

1. Review the two accepted recordings' actual original Native/map/device sources if locally supplied. Establish the same statutory roadway crossing and any 30-foot separate-roadway distinction before selecting new captures.
2. Bind a reviewed OpenDRIVE map and highway/device citations to exact constructions, controllers, four-camera 20 Hz acquisition, source manifest and saved-only finalization.
3. Complete semantic proposals, source-bound positive/negative compatibility, process-saved fixtures, independent delivery audits and physical-risk candidate assessment. Preserve official-device and subsection-4 uncertainty.
4. Rerun the exact scoped strict gate; no ready status follows from synthetic tests or accepted metadata alone.

## Proven checks and dependency boundary

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125763__NRS-484B-250-1__motor_vehicle_driver/tests -v` passed 8 focused tests (`cpu-tests.log`, SHA256 `8ed9a2333bc1b26d297954836c211791924f5d62331c154bcd7a17dab5848a9e`). Assignment static check passed (`static-check.log`, SHA256 `8e351fab1c87eb51f7818dbc5444575c355109365bbb767d50b015e9a778edfa`). Exact `.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-1__motor_vehicle_driver --complete --require-delivery-ready` exited 1 in `strict-check.log`: partial/missing packages remain. These software tests do not prove physical or legal acceptance. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
