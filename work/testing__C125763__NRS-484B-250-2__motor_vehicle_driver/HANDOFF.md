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
