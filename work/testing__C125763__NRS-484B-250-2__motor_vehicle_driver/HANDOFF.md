# testing__C125763__NRS-484B-250-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.250(2); with 484B.250(5) — When two vehicles enter an intersection from different highways at approximately the same time, the driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Measured crossing-entry timing at a median-opening intersection..
Cell: C125763 (median_opening, travel, yield_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 1. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 1 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU construction checkpoint

The exact law's subsection 5 excludes official-device-controlled intersections except as subsection 4 provides. The fixed C125763 cell has a yield sign. Neither the accepted metadata nor the exported review context establishes a subsection 4 basis or original entry times. Consequently none of the two accepted IDs is claimed as measured 250(2) coverage and no legal priority/"approximately same time" finding is made.

`case-plan.json` now declares three new requested timing probes, `__entry_below`, `__entry_inside`, and `__entry_above`, using the source-hashed physical training targets in `judgment-probe-plan.json`. Comparison `entry_timing_range` fixes the site, device status, approach roles, actor setup and capture policy while varying requested other-vehicle release timing. The requested values are unmeasured engineering targets. This plan must be reconciled with the official-device exception before delivery can be ready; the exact selected scope has not been changed.

`native_construction.py` now reads a separately reviewed source packet, verifies live OpenDRIVE and retained device/highway source bytes, validates both original approach lanes and headings, lazily spawns both CARLA vehicles, cleans up a first spawn if the second fails, and applies a bounded release/route-heading controller without relocating actors. `crossing_timing.py` computes first footprint-intersection transitions from source-hashed original Native histories, checks a contiguous 20 Hz same-frame/time/actor join and map identity, reports the ego-minus-other upper timestamp with sampling bracket, and leaves legal applicability and judgment unresolved. Synthetic fixtures test both approach directions, source/map/lane rejection, holding/release control, timing, and missing/stale data. They do not establish Native motion or accepted evidence.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/tests -v` passed 7 tests; `cpu-tests.log` SHA-256 `c10337e2516344d220354a3fd04b8370883330c4115df56d7d982887ceb71c15`. The exact strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` exited 1 at the truthful partial-package acceptance check; `strict-gate.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Remaining CPU work: reconcile the source-reviewed subsection 4 applicability in this fixed yield-sign cell; complete live capture/camera/trace integration and exact case bundles, saved finalization, semantic proposals, positive/negative compatibility receipts, independent delivery and comparison audits, and risk-based candidate review. Then rerun each exact case proof and the strict assignment gate. Actual physical motion, pixels and original source review remain later local verification, not excuses for the unfinished CPU package.

## 2026-11-23 original-frame capture checkpoint

`native_history_capture.py` now takes the reviewed site packet and a synchronous 20 Hz CARLA world with two owned actors. It verifies the live OpenDRIVE and original device/highway source hashes through `reviewed_scene`, distinct actor identities, finite reviewed intersection bounds, and world fixed delta. For each tick it retains the original snapshot frame and elapsed time and computes each vehicle's XY convex hull from all eight live CARLA bounding-box vertices. It rejects frame/time discontinuity and seals `site-context.json`, `road.xodr`, both body histories and their SHA-256 manifest without overwriting an existing capture. The output feeds `crossing_timing.measure`; it is not itself a full Native result or four-camera recording. The fake-world tests do not establish CARLA behavior, pixels or legal applicability.

`native_history_capture.py` SHA-256 `83794d79f7149a0da3807f481211736dd8999abecd529674d0c2aa07045e0372`; `tests/test_native_history_capture.py` SHA-256 `7a5d4f2ad66670bf7b719b040266a0096a054f92a91055cefa68fba6da8b9b30`. `PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work/c125763-tmp SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c125763-pipeline .venv-cpu/bin/python -m unittest discover -s work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/tests -v` passed 11 tests; `cpu-tests.log` SHA-256 `3dc33b18aed94e0ae435f4e637a46e0d6f862e94623a2994011b130cf6afced5`. Pinned `runtime.py preflight` passed, `preflight.log` SHA-256 `dd9c82ac31e60377d2d0292d600b59985fbbbc7078e44c9811945f96fb10f845`. Scoped `worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete` passed static, `scoped-static.log` SHA-256 `e86abda95bb7765cb72cb835dc61ab64d11c0e50f4d86142b2e0f50e209899d6`. Exact scoped strict with `--require-delivery-ready` exited 1 because this package remains partial, `strict-gate.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Next CPU work: bind the live history sealer to a four-camera synchronized acquisition and native frame map; implement an exact saved result finalizer and case-specific positive/negative compatibility; author semantic proposals and independent delivery/comparison audits. Review the exact subsection 4 text and source basis for the fixed yield-sign cell before making any 250(2) applicability or priority claim. Then complete all three exact case bundles and rerun the strict gate. Status remains partial.

## 2026-11-24 saved entry finalizer checkpoint

`saved_finalizer.py` now accepts only the three exact planned timing probes, verifies the source-manifest SHA, reruns original body-history entry measurement, and writes a once-only result bound to source hashes. It records the frame count and flags short diagnostic fixtures while explicitly leaving camera coverage, physical acceptance, subsection 4 applicability and legal judgment unresolved. The focused fixture tests reject stale manifest/source bytes and overwrite attempts.

The focused suite passed 13 tests; pinned preflight and scoped static passed; exact scoped strict exited 1 on truthful partial. Commands and SHA-bound logs are in `result.json`. Remaining CPU work: source-reviewed subsection 4 applicability in the fixed yield-sign cell, synchronized four-camera Native capture, three canonical case bundles, semantic proposals, offline/compatibility and independent saved delivery/comparison audit.
