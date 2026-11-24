# testing__C104081__NRS-484B-297-6__pedestrian

Status: partial CPU construction and comparison-audit checkpoint. The strict assignment gate remains open; no physical or legal acceptance is claimed.

Exact law: NRS 484B.297(6) — A pedestrian walking or otherwise traveling on a sidewalk who encounters an obstruction to his or her mobility on the sidewalk, including, without limitation, a short section of the sidewalk that is missing or impassable, may proceed with due care on the immediately adjacent highway to move around such an obstruction. Such a pedestrian: (a) Must walk or otherwise travel as far to the side of the highway near the sidewalk as possible; (b) May walk or otherwise travel on the highway in the direction he or she was walking or traveling on the sidewalk, regardless of the direction of traffic; (c) May walk or otherwise travel in a lane provided for bicycles, electric bicycles or electric scooters if the area between the lane and the sidewalk is impassable; and (d) Must return to the sidewalk as soon as practicable.
Assigned branch(es): Adjacent designated-lane bypass with intervening-area physical variations..
Cell: C104081 (hill_crest, travel, obstruction); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## 2026-11-23 measured Native walking controller checkpoint

`native_walking.py` now accepts the exact constructed route and SHA-bound surveyed local-to-world transform. Its 900-tick, 20 Hz `WalkerControl` loop requests movement but records original pose/frame/time readback, rejects wrong start, stale frames, stalled movement and route departure, verifies a measured endpoint, and commands a stop in `finally`. `native_construction.construct_native` retains the checked route and survey digest for that bridge. The controller leaves due care, side-as-possible and practicability unresolved.

`tests/test_native_walking.py` exercises completed measured movement, stale/missing motion, route departure, invalid start, wrong duration and changed survey bytes. The full focused suite passes 66 tests; pinned CPU preflight passes. This is a CPU fake-world proof of the route controller and source bridge, not actual CARLA motion or camera evidence. The complete CARLA adapter, four-camera Native capture, exact inline bundles and semantic/compatibility/saved delivery proofs remain to be authored.

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

## 2026-11-23 five-case diagnostic bundle checkpoint

`build_offline_draft.py` packages every exact planned bypass case with the current geometry, surveyed-map construction, measured Native walking controller, saved measurements and independent audits. Its bundled runner hashes the case plan, checks each case parameter and 20-Hz/900-frame/four-camera profile, constructs and audits the actual sidewalk obstruction, intervening barrier and bicycle-lane route as applicable, then refuses unsurveyed Native capture. The five pinned `runtime.py offline` runs passed with generated materializations under `.runtime-work/`. The 67-test focused suite and pinned preflight passed. This is a diagnostic draft, not a canonical delivery manifest or physical evidence.

Proof SHA-256 (logs under this assignment):

- `cpu-preflight.log`: `29ca0d02d380b4d67cec6fffcba275e9a10b606c3c1aad962136ec86aa7c8c11` (exit 0)
- `cpu-tests.log`: `8e503fbdf3e4c71ce378256eb1a865ca17330adf93edbd59c48da880c8f2495c` (exit 0)
- `cpu-static-check.log`: `f7ae058c828bf483f5ae261c3eeab547c77f7393c695b92673bf338ea14b63a4` (exit 0)
- `cpu-strict-gate.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-clear_intervening.log`: `b134975dcdc076d4ff129270dcccc2610809d16d30784b0d289fc92f8e7efbf6` (exit 0)
- `cpu-offline-blocked_intervening.log`: `5425f4fee5fe57f1f743432233e8e81a3fe82f75e8926bf006c0af3d86de4b73` (exit 0)
- `cpu-offline-blocked_opposite.log`: `aa378dc7d2e0cbf4ceed29d82d7fa033f72994d208648a26d08ba60f2a141f56` (exit 0)
- `cpu-offline-blocked_late_return.log`: `70611cf3d3a5e96acdc688342e50d016e1fd90a30eb7b976234105e4a0258e62` (exit 0)
- `cpu-offline-missing_sidewalk.log`: `d933451a9090d94e3f0d92e0533c054e0ac593895b00bd3fcdb2a3c080ba28e0` (exit 0)

Next CPU work: bind a surveyed Native hill-crest site and four-camera capture to the constructed pedestrian route; author canonical semantic proposals and manifest; run exact source-shaped positive/negative compatibility, saved-only and independent delivery/comparison receipts for each case. Actual route visibility, due care, side-as-possible and return practicability remain unverified. The scoped strict command fails on truthful `partial` status.

## 2026-11-23 synchronized Native source packet checkpoint

`native_walking.py` now invokes an observer after each measured world tick and stops the walker if a source read fails. `native_source_packet.py` joins all four original-shaped readbacks to that tick, rejects frame/time discontinuity, requires the SHA-bound original C104081 survey and exact case, and seals the five sources expected by `saved_measurement.py` after exactly 900 samples. `capture_constructed_sources` connects the measured route to a caller-supplied Native source reader. The writer does not replace observed positions with route targets. The caller must still supply actual CARLA actor, obstacle, traffic and camera readbacks and own lifecycle cleanup; its original-source label requires local ownership review and cannot itself authenticate provenance.

The builder regenerated all five exact diagnostic constructions with this bridge and refreshed their manifest hashes. Pinned preflight, 72 focused tests, five exact `runtime.py offline` runs, and the scoped static check pass. The scoped strict delivery check still exits 1 on truthful `partial` status; no physical or legal acceptance follows. Current proof commands, exit codes, log paths and SHA-256 values are in `result.json`.

Next CPU actions: implement the concrete CARLA source reader and four-camera acquisition/encoding; bind source packet output into Native finalization, then author canonical proposals, exact positive/negative compatibility recipes, saved-only processing and delivery/comparison receipts for all five cases. Rerun the exact strict assignment command after those proofs.

## 2026-11-23 observed actor and camera frame checkpoint

`native_readback.py` is a lazy CARLA-facing readback from actual actor bounding boxes, observed obstacle/barrier handles, original surveyed missing-surface polygon, live traffic roster and four synchronized camera sensor frame IDs. It derives the sidewalk obstruction end from observed world vertices and the source-bound transform, and rejects a stale camera, absent traffic roster, missing actor or body position that differs from the walking controller's measured tick. It can feed `capture_constructed_sources` for all five exact cases. The camera synchronizer still has to retain original pixel payloads; this layer checks frame identity only.

The five offline bundles were regenerated and their hashes refreshed. Current `result.json` binds passing pinned preflight, 76 focused tests, five exact offline constructions and scoped static check. The exact scoped strict gate exits 1 because status remains partial. The next CPU construction step is a concrete camera payload collector/encoder and Native lifecycle/finalizer, followed by canonical proposals, compatibility, saved-only processing, and delivery/comparison receipts for each exact case. No physical visibility, legal due care, side-as-possible or practicability has been established.

## 2026-11-23 camera contract alignment

The five exact diagnostic bundles and `native_readback.py` now require `overview`, `approach`, `reference_corner` and `driver_reference`, matching the independent delivery auditor's sealed media names and intended 1920×1080/1280×720 profile. Earlier front/rear/left/right draft names would have failed saved delivery. All five offline constructions were regenerated and retested; current passing receipts and hashes are in `result.json`. The camera synchronizer must still retain pixel payloads and encode original videos before delivery can pass.
