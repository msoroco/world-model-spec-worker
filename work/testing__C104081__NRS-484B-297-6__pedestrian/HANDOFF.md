# testing__C104081__NRS-484B-297-6__pedestrian

Status: partial CPU construction and comparison-audit checkpoint. The strict assignment gate remains open; no physical or legal acceptance is claimed.

Exact law: NRS 484B.297(6) — A pedestrian walking or otherwise traveling on a sidewalk who encounters an obstruction to his or her mobility on the sidewalk, including, without limitation, a short section of the sidewalk that is missing or impassable, may proceed with due care on the immediately adjacent highway to move around such an obstruction. Such a pedestrian: (a) Must walk or otherwise travel as far to the side of the highway near the sidewalk as possible; (b) May walk or otherwise travel on the highway in the direction he or she was walking or traveling on the sidewalk, regardless of the direction of traffic; (c) May walk or otherwise travel in a lane provided for bicycles, electric bicycles or electric scooters if the area between the lane and the sidewalk is impassable; and (d) Must return to the sidewalk as soon as practicable.
Assigned branch(es): Adjacent designated-lane bypass with intervening-area physical variations..
Cell: C104081 (hill_crest, travel, obstruction); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Current constructed plan

`case-plan.json` now specifies five exact cases: `__clear_intervening`, `__blocked_intervening`, `__blocked_opposite`, `__blocked_late_return`, and `__missing_sidewalk`, each prefixed by this assignment ID. It specifies four controlled comparisons: intervening-area condition, travel direction, sidewalk-return opportunity, and sidewalk-obstruction type. Every case carries source gap IDs and a physical-risk assessment. Frozen `evidence.json` has zero accepted recordings, so source-backed reuse is unavailable. No judgment range entry matches this law and actor, and no numeric legal cutoff is assumed.

`geometry.py` constructs distinct sidewalk, intervening area, designated bicycle lane and adjacent highway rectangles, an actual sidewalk obstruction, optional intervening barrier, and pedestrian routes in both longitudinal directions. Its design audit samples each path and rejects obstacle intersection, missing barriers, misaligned boundaries and wrong lane use. The coordinates are local engineering metres awaiting surveyed CARLA map binding; no physical feasibility is asserted.

`comparison_audit.py` independently requires original saved-acquisition packets and matching SHA-256 values. It rejects missing cases, synthetic-source labels, changed fixed conditions and undeclared differences. It reports source consistency only; due care, far-to-side, impassability and as-soon-as-practicable remain unresolved judgments.

`native_construction.py` now requires a SHA-bound original Native map survey naming the exact C104081 hill-crest map, sidewalk, intervening area, designated bicycle lane, adjacent highway and local-to-world transform before any actor creation. It calls explicit adapter methods to spawn the pedestrian, sidewalk obstruction and optional intervening barrier, set the route and read back the created resources. The missing-sidewalk variant requires a surveyed existing surface gap and never substitutes a fake obstacle. A route-control or readback failure destroys owned handles in reverse order. No actual site survey or CARLA adapter has been bound; these CPU spy tests prove call order and rejection behavior only.

## Next CPU actions

1. Bind the authored cross section to a surveyed Native sidewalk/highway/bicycle-lane map; implement the CARLA adapter, capture, world snapshot/restore and finalization.
2. Author source-bound measurement contracts and positive/negative compatibility receipts for all exact cases, canonical semantic proposals, saved-only processing and the independent delivery audit. Wire `comparison_audit.py` to original measured packets.
3. Review the exact law and clause alternatives independently, then repair any missing cases or comparisons. Keep all judgments unresolved pending source evidence.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C104081__NRS-484B-297-6__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`cpu-preflight.log`: `.venv-cpu/bin/python runtime.py preflight` passed. `cpu-tests.log`: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C104081__NRS-484B-297-6__pedestrian/tests -v` passed 21 tests, including negative geometry, survey, actor cleanup and source-audit branches. `cpu-static-check.log`: the assignment `worker_check.py --complete` passed. `cpu-strict-gate.log`: exact assignment `--complete --require-delivery-ready` failed because the status is correctly partial. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Saved-source measurement checkpoint

`saved_measurement.py` reads only files named and SHA-256 sealed by `source-packet.json`: the original map survey, 20 Hz frame map, walker body vertices, observed obstruction polygons and traffic history. It transforms world vertices into the surveyed local cross section; joins all streams by original frame and time; derives designated-lane occupancy, pedestrian direction, center distance to the sidewalk edge, observed obstruction and intervening-barrier bounds, and the first sidewalk-return frame. An absent physical barrier polygon, an obstruction extent mismatch, missing source, changed bytes, wrong cadence or broken frame join is rejected. `comparison_projection` derives the earlier comparison-audit packet from those histories while retaining fixture provenance. A synthetic fixture remains ineligible for the original-source comparison audit and is never physical evidence. `measurement-contract.json` maps each statutory clause to its selected sources and observable; due care, side-as-possible, area impassability and practicability are unresolved judgments.

Run the CPU proof with `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C104081__NRS-484B-297-6__pedestrian/tests -v`. The remaining construction and delivery items above are still actionable CPU work; no readiness claim follows from this measurement checkpoint.

`comparison_audit.audit_saved_attempts` now reads exact sealed attempt roots through `comparison_projection`, rejects diagnostic fixtures and mismatched case identities, then applies the fixed-condition and deliberate-difference audit. It remains a software source-consistency check, not a legal or physical acceptance audit. The attempt's capture-context hashes must originate from actual acquisition, so local execution must bind them before relying on the projection.

## 2026-11-23 saved-attempt audit checkpoint

`delivery_audit.py` independently reads each exact attempt's sealed sources through `saved_measurement.measure_saved`, requires 900 contiguous original CARLA frames at 20 Hz, and compares the measured direction, barrier, bicycle-lane use, obstruction extent and kind against the exact planned case. It requires four distinct attempt-local camera files with matching SHA-256, 900 declared frames and 20 Hz metadata. The default rejects diagnostic input; an explicit diagnostic mode exists solely for CPU fixture tests. The return receipt sets `full_video_decode`, `actual_pixels`, `all_participants` and `physical_completion` false. Media bytes and metadata cannot establish those conditions; a local decoder and physical source review still need implementation. A forged source label cannot be authenticated by this standalone audit without a sealed Native lifecycle receipt.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C104081__NRS-484B-297-6__pedestrian/tests -v` passes 59 focused tests, including wrong-case relabeling, incomplete frame history, missing camera, media tamper and path escape. `.venv-cpu/bin/python runtime.py preflight` and the assignment `worker_check.py --complete` pass. The exact assignment `--complete --require-delivery-ready` fails on the truthful partial status. Logs and hashes are in `result.json`.

Next CPU work: bind the surveyed CARLA map and actual adapter; implement synchronized Native capture and finalization; author exact semantic proposals and positive/negative compatibility recipes for all five cases; bind this audit to sealed Native lifecycle evidence and inspect physical content; add saved-only processing and manifest-bound delivery/comparison proof receipts. Run the exact strict assignment gate after those proofs. No readiness or physical acceptance is claimed at this checkpoint.

## 2026-11-23 full media-decode extension

`delivery_audit.py --attempt PATH --case ID --decode-media` now uses FFprobe to count the original frames and verify 20 Hz, then FFmpeg to decode the entire first video stream of each of the four sealed camera files. Original attempts require the pinned overview 1920×1080 and three 1280×720 dimensions. Explicit `--diagnostic` permits a small synthetic video fixture and returns its profile-dimension mismatch, while still leaving `actual_pixels`, participant visibility and physical completion false. A sealed text file is rejected when decode is requested. The CLI's default provenance check rejects synthetic input. These are software proof branches; local Native ownership and scene content remain unverified.

The focused suite now passes 62 tests. The CPU diagnostic videos are generated only in temporary test directories and are not returned files. The remaining CPU work still includes real CARLA map binding, synchronized capture and Native finalizer, canonical proposals, exact per-case compatibility and manifest post-capture integration, plus physical-content and lifecycle audit logic. The 900-frame source audit and full decode are reusable components for that work; this package remains partial.
