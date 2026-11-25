# testing__C125697__NRS-484B-250-2__motor_vehicle_driver

Status: CPU delivery prepared for four exact cases after the full camera decode repair below. Earlier sections record the initial source inventory and construction history.

Exact law: NRS 484B.250(2); with 484B.250(5) — When two vehicles enter an intersection from different highways at approximately the same time, the driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Measured crossing-entry timing at a median-opening intersection..
Cell: C125697 (median_opening, travel, inoperative_signal); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 1. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 1 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU construction checkpoint

- Added four exact cases to `case-plan.json`: `timing_below_training`, `timing_inside_training`, `timing_above_training`, and `right_approach_inside`, all prefixed by the assignment ID. The first three use source-hashed training bounds (-2.0500000305473804 to 2.0000000298023224 s) and unmeasured targets -2.860000042617321, -0.02500000037252903, and 2.810000041872263 s. These values are physical coverage targets only; no legal cutoff or outcome is asserted. Two comparisons hold crossing geometry, straight movement, and inoperative signal fixed while varying timing or approach side. `construction-targets.json` lists route, controller and Native source requirements and a concrete physical-risk assessment.
- `entry_timing.py` measures both first footprint-intersection entry transitions from consecutive original frames, retains lower/upper frame and time brackets without interpolation, and reports ego minus other upper timestamp. It rejects missing original frames, missing participant states, same-highway routes, unknown left/right relation, unresolved opposite-approach or official-device exceptions, or a signal lacking inoperative readback. Its comparison audit checks exact case IDs, source hashes and fixed road, movement, signal and exception context. This is a source-shaped software proof, not an original recording.
- `footprint_capture.py` lazily samples live Native actor bounding-box world vertices and tests polygon overlap against a verified intersection polygon supplied by the runner. It requires both actors alive and distinct. The actual median-opening map polygon, route association, signal readback, full runner and sealed packet writer remain to construct and verify.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/tests -v` passed six tests; see `cpu-tests.log` and its SHA in `result.json`. Exact static gate passed; exact strict delivery-ready gate failed at partial/missing packages, as expected for `status: partial`. See `static-check.log` and `strict-check.log`.
- Independent law reread: subsection 2 applies to different highways and left/right crossing approach at approximately simultaneous entry. The official-control and opposite-direction left-turn exceptions, with subsection 4 override, require compatible additional cells and source review; this fixed travel/inoperative-signal cell must not fabricate their applicability. Accepted `precedence` and `advance` membership metadata cannot prove realized entry timing or comparison isolation without original trace/video.

Next CPU work: bind and verify Native median-opening intersection polygon and two crossing route IDs; complete configuration-driven CARLA runner and sealed 20 Hz source packet; finish semantic proposals, case-specific positive/negative compatibility and saved-only processing, independent delivery and comparison audits, and exact-case manifest/candidate proofs. Do not mark ready before the strict gate passes.
# 2026-11-25 exact delivery preparation

The current package is CPU delivery prepared. The exact scoped command
`.venv-cpu/bin/python worker_check.py --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready`
passed after the final source, manifest, semantic, physical, compatibility,
delivery-audit, and test bindings were written. This is a preparation gate;
original Native execution, visible four-view footage, and statutory judgment
remain to be checked on the selected local job.

Four selected cases are `timing_below_training`, `timing_inside_training`,
`timing_above_training`, and `right_approach_inside`, each prefixed by this
assignment ID. Their requested timing offsets are source-hashed training
coverage targets, not legal thresholds. The right-approach case swaps the
vehicle roles on the same two highways and fixes the interior timing request.
The controlled comparisons are `left_approach_entry_timing_training_range`
and `entry_side_relation`. The saved comparison script and diagnostic receipts
are in `saved_comparison.py` and `comparison-{timing,side}-diagnostic.json`.
The diagnostic results establish source-bound CPU comparison behavior only.

`execution-manifest.json` binds all four exact constructions, one source-hashed
lower-speed physical fallback per case, eight successful offline checks, eight
positive/negative compatibility paths, four saved-only processing paths,
four physical complete/incomplete/missing fixtures, and four positive plus
camera-tamper audit probes. `cpu-tests-current.log` records 15 passing focused
tests. The source-gated Native capture requires a reviewed original CARLA
roadway crossing packet with OpenDRIVE geometry, distinct public-highway
identities, governing inoperative official-signal readback, approach routes,
subsection 4/opposing-turn review, and four camera poses. It records 900
20 Hz original frames. `delivery_audit.py` independently checks original
source hashes, body/camera time joins, ownership closure, saved processing,
physical completion and visible pixels. The nine-frame software fixtures
cannot satisfy this production audit.

The two frozen accepted recordings supplied only metadata. Their review facts
cite each recording's frozen metadata source; the absent original video/trace
cannot establish physical equivalence. No legal verdict or original physical
acceptance is claimed. The lead should queue all four exact cases and the two
comparison audits after its independent review. Scratch attempts and videos
are under `.runtime-work/c125697-2502/final-proof-v6` and are not returned.

## 2026-11-25 original camera decode repair

The production `delivery_audit.py` now independently decodes every RGB frame
of each of the four original FFV1 videos. It checks 1920x1080 overview and
1280x720 remaining camera dimensions, 20 fps, exactly 900 decoded frames,
visible pixel variation in each frame, and each camera's 900-row Native
frame map against `video_frames.jsonl`. It compares decoded frames 0, 450 and
899 byte for byte with original PNGs retained by `native_capture.py`; those
PNGs, frame maps and videos must all be present in the capture seal. The
delivery receipt reports a full decoded RGB stream SHA per camera under
`original_video_decode`, replacing the first-frame-only pixel digest.

The focused test changes a middle video frame while retaining the sealed
middle PNG, shortens the video to eight of nine diagnostic frames, and
changes a camera frame-map join; all three are rejected. The 16 focused CPU
tests pass. Rebuilt primary and fallback constructions passed all eight
offline and eight positive/negative compatibility checks. Four positive and
four camera-tamper delivery probes were refreshed; `execution-manifest.json`
and its bound proof receipts were regenerated for the new construction hashes.
The exact scoped command
`.venv-cpu/bin/python worker_check.py --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready`
passed with exit 0. The original 900-frame Native footage still requires the
selected local CARLA job; diagnostic footage is not physical acceptance.
