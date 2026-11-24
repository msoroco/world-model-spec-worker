# testing__C125714__NRS-484B-250-2__motor_vehicle_driver

Status: partial source-bound measurement implementation. Three unexecuted timing coverage probes are planned; no new recording or physical acceptance is claimed.

Exact law: NRS 484B.250(2); with 484B.250(5) — When two vehicles enter an intersection from different highways at approximately the same time, the driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Measured crossing-entry timing at a median-opening intersection..
Cell: C125714 (median_opening, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 8. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 1. Bounds are training coverage targets, not legal cutoffs.

## CPU implementation and exact planned probes

- `native_body_capture.py` captures both distinct live actors' ordered world-space bounding-box footprints from the same original world snapshot. It fails on missing/dead actors, invalid coordinates or frame/time identity; it never creates site geometry or legal context.
- `entry_timing.py` requires a SHA256-bound original Native map, reviewed site context and two 20 Hz body histories. It validates exact actor and frame/time joins, convex intersection and footprint polygons, and first outside-to-inside body entry for both actors. It retains consecutive sample brackets without interpolation and never assigns a legal interpretation to “approximately the same time.” Its pair auditor checks fixed crossing, roadway and exception context against the declared timing variable.
- `case-plan.json` now names `__timing_below_training`, `__timing_inside_training` and `__timing_above_training`, with source-hashed training targets -2.860000042617321 s, -0.02500000037252903 s and 2.810000041872263 s. These are requested physical coverage values, not measured samples or legal thresholds. `median_opening_entry_timing_training_range` holds map, approaches, devices, cameras and duration fixed. The prior eight accepted metadata entries remain reviewed as metadata only; they do not establish source-bound equivalence or remove a recording need.
- The official-device exception, opposite-approach left-turn exception, separate-roadway crossing distinction, and subsection-4 qualification remain unresolved in the plan. The source-bound software currently measures crossing and opposite context, but no exact executable construction or delivery proof exists.

## Next CPU actions

1. Independently review the complete original law and the eight accepted original trace/video sources if made available. Resolve evidence sufficiency and physical geometry before selecting new recordings; preserve the frozen accepted metadata.
2. Build the exact median-opening highway intersection, both approach directions, lower-level vehicle controllers and per-case 20 Hz four-camera capture. Bind the reviewed map/site authority rather than treating a median opening label as an intersection.
3. Expand the three timing probes and exception alternatives to complete inline constructions, source-bound finalizers, semantic proposals, positive/negative compatibility, saved-only processing, physical-risk candidates where justified, and independent delivery/comparison audits.
4. Run the exact assignment strict gate after these CPU deliverables and repair failures. Do not mark ready from these synthetic software tests.

## Proven checks and dependency boundary

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/tests -v` passed 8 focused CPU tests (`cpu-tests.log`, SHA256 `15c687131fd9c75365c7c4b65674d74f4240934f19325af73e5fbecb7876129b`). Assignment static check passed (`static-check.log`, SHA256 `cc5926eaa4badf150cb317b2f4af80f7a581d99334be67c65f61d736bbe79873`). Exact scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` exited 1 in `strict-check.log`: partial/missing packages remain. Synthetic tests prove only arithmetic and software rejection branches, not a real source review or physical event. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 1 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
