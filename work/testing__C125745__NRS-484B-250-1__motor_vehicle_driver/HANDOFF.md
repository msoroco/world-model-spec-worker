# testing__C125745__NRS-484B-250-1__motor_vehicle_driver

Status: partial exact-pair source-bound measurement. Two prior accepted case IDs are retained for original-source review; no new recording or physical acceptance is claimed.

Exact law: NRS 484B.250(1); with 484B.250(5) — The driver of a vehicle approaching an intersection shall yield the right-of-way to a vehicle which has entered the intersection from a different highway. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Other vehicle enters the same statutory roadway crossing at a median opening before ego..
Cell: C125745 (median_opening, travel, stop_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU implementation and evidence limits

- `saved_crossing.py` requires SHA256-bound `road.xodr`, `site-context.json`, and complete ego/other original Native body histories. It verifies reviewed map identity, different highway identities, the fixed C125745 stop sign, explicit governance and subsection-4 review status, distinct actor IDs, contiguous synchronized 20 Hz frames, convex original body and crossing geometry, both body entries and exits, and simultaneous occupancy. It retains original transition brackets and reports `other_entered_before_ego` and `other_cleared_before_ego_entry`. It issues no legal applicability or compliance finding.
- Its pair audit checks that the same crossing, roadway, other-vehicle entry/exit, official-device governance, subsection-4 status, approaches and frame count stayed fixed while the measured ego clearance order changes. Tests reject missing/stale original sources, incomplete trajectories, changed context, bad joins and identity mismatches.
- `native_crossing.py` samples both actors' original world-space bounding boxes on one Native tick and provides bounded hold/route-follow vehicle control. The route must later be bound to a reviewed real map and exercised in CARLA; requested control is not realized behavior.
- `case-plan.json` now lists exact `__precedence` and `__advance` case IDs, their frozen accepted recording IDs and `official_stop_precedence` controlled comparison. Frozen metadata says both were accepted with 1,100 frames, but their original video, trace, site geometry and local delivery-audit bytes are not in this export. Their law-specific physical measurements and pair isolation remain unverified. Because this cell's fixed control is `stop_sign`, the subsection-5 official-device exception and unresolved subsection-4 qualification remain explicit.

## Next CPU actions

1. Review the two accepted recordings' actual original Native/map/device sources if locally supplied. Verify the same statutory roadway crossing and separate-roadway geometry rather than inferring from metadata or a median opening label.
2. Bind a reviewed OpenDRIVE map and highway/device source citations to exact constructions, controllers, four-camera 20 Hz acquisition, source manifest and saved-only finalization. Determine whether existing evidence suffices before requesting any new capture.
3. Complete semantic proposals, source-bound positive/negative compatibility, process-saved fixtures, independent delivery audits and risk-based fallback assessment. Preserve official-device and subsection-4 uncertainty.
4. Rerun the exact scoped strict gate; no ready status is justified by synthetic tests or accepted metadata alone.

## Proven checks and dependency boundary

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-1__motor_vehicle_driver/tests -v` passed 8 focused tests (`cpu-tests.log`, SHA256 `effe3dc866df8a74869260bb37c075ec473f02e1d4384e865b1c27f7bba93485`). Assignment static check passed (`static-check.log`, SHA256 `fc3939f8f06d63a0dd90ce576a842753948dab29301efcba53548019ad2ffa6a`). The exact `.venv-cpu/bin/python worker_check.py --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --complete --require-delivery-ready` command exited 1 in `strict-check.log`: partial/missing packages remain. These are software tests, not physical or legal acceptance. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
