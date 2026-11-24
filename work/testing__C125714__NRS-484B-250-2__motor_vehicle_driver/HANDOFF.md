# testing__C125714__NRS-484B-250-2__motor_vehicle_driver

Status: partial source-bound construction, selected measurement and semantic draft. Three unexecuted timing coverage probes are planned; no new recording or physical acceptance is claimed.

Exact law: NRS 484B.250(2); with 484B.250(5) — When two vehicles enter an intersection from different highways at approximately the same time, the driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Measured crossing-entry timing at a median-opening intersection..
Cell: C125714 (median_opening, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 8. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 1. Bounds are training coverage targets, not legal cutoffs.

## 2026-11-23 return pass: executable crossing and selected diagnostic

- `native_crossing.py` now checks a live OpenDRIVE hash, two source-reviewed different-highway routes reaching the same crossing, left/right approach identity, device/turn/subsection-4 context, distinct vehicle spawns and route readback. It rolls back failed actors. `apply_timing` controls two release schedules as requested engineering targets; actual entry timing is measured independently from original footprints.
- `saved_finalizer.py` binds one of the three exact timing cases to sealed original map, site and body histories; it rejects wrong cases, missing sources and unsupported exception contexts. It returns entry brackets and leaves legal timing/yielding unresolved.
- `comparison_audit.py` independently checks all three source-bound diagnostics, fixed crossing/roadway/approach/device context, identical original map bytes and ordered measured timing differences. Case-specific site-context hashes may differ because case IDs differ.
- `proposals/` now has draft relevance, template, bindings, cases, judgment observables and a hashed semantic index. `case-plan.json` names the selected requirement and pending exception alternatives. Fourteen focused CPU tests pass; static scoped check passes.
- Remaining CPU work: actual reviewed C125714 physical map and routes; canonical runner/config/construction manifest with four synchronized cameras; complete exception and yielding cases; per-case offline and positive/negative compatibility receipts; source-bound saved delivery and independent delivery audit. No runtime compatibility or physical acceptance is claimed from the focused fixture tests.

## CPU implementation and exact planned probes

- `native_body_capture.py` captures both distinct live actors' ordered world-space bounding-box footprints from the same original world snapshot. It fails on missing/dead actors, invalid coordinates or frame/time identity; it never creates site geometry or legal context.
- `entry_timing.py` requires a SHA256-bound original Native map, reviewed site context and two 20 Hz body histories. It validates exact actor and frame/time joins, convex intersection and footprint polygons, and first outside-to-inside body entry for both actors. It retains consecutive sample brackets without interpolation and never assigns a legal interpretation to “approximately the same time.” Its pair auditor checks fixed crossing, roadway and exception context against the declared timing variable.
- `case-plan.json` now names `__timing_below_training`, `__timing_inside_training` and `__timing_above_training`, with source-hashed training targets -2.860000042617321 s, -0.02500000037252903 s and 2.810000041872263 s. These are requested physical coverage values, not measured samples or legal thresholds. `median_opening_entry_timing_training_range` holds map, approaches, devices, cameras and duration fixed. The prior eight accepted metadata entries remain reviewed as metadata only; they do not establish source-bound equivalence or remove a recording need.
- The official-device exception, opposite-approach left-turn exception, separate-roadway crossing distinction, and subsection-4 qualification remain unresolved in the plan. The source-bound software measures crossing and opposite context; selected crossing construction exists, while full delivery proof is pending.

## Next CPU actions

1. Independently review the complete original law and the eight accepted original trace/video sources if made available. Resolve evidence sufficiency and physical geometry before selecting new recordings; preserve the frozen accepted metadata.
2. Bind a source-reviewed physical median-opening highway intersection and both approach routes to the constructor, then complete the canonical runner and per-case 20 Hz four-camera capture. A median-opening label alone is not an intersection proof.
3. Expand the three timing probes and exception alternatives to complete inline constructions, runtime positive/negative compatibility, saved-only processing, physical-risk candidates where justified and independent delivery audit. Selected diagnostic, draft semantic proposals and an independent timing comparison audit now exist.
4. Run the exact assignment strict gate after these CPU deliverables and repair failures. Do not mark ready from these synthetic software tests.

## Proven checks and dependency boundary

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/tests -v` passed 14 focused CPU tests (`cpu-tests.log`). Assignment static check passed (`static-check.log`). Exact scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` exited 1 in `strict-check.log`: partial/missing packages remain. Current log hashes are in `result.json`. Synthetic tests prove construction/finalizer/audit rejection branches only, not real-source review or physical events. CARLA is needed after CPU preparation for actual motion and video verification.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 1 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.
