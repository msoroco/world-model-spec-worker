# testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.040(A) — Except as otherwise provided in this Chapter: No person shall stand or park a vehicle in a roadway other than parallel with the edge of the roadway headed in the direction of lawful traffic movement.
Assigned branch(es): parallel orientation and lawful heading.
Cell: C150041 (one_way_road, parallel_park, road_edge); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-22 six-case parking geometry construction start

`case-plan.json` now proposes six exact case IDs: `__park_parallel_lawful`, `__park_angled_lawful`, `__park_parallel_reverse`, `__stand_parallel_lawful`, `__stand_angled_lawful`, and `__stand_parallel_reverse`. Four controlled comparisons hold the activity and other setup conditions fixed while changing requested orientation or heading. These are draft cases, with no recording or physical realization claimed. The shared baseline is reused within each activity, and no numerical legal angle or curb-distance threshold was introduced.

`parking_measurement.py` reads source-hashed original body frames and reports nearest-edge distance, absolute parallel deviation, lawful-heading deviation, heading dot product and count of original body corners inside the roadway. It requires an ordered frame/time series and source-described edge, roadway and lawful direction. `tests/test_parking_measurement.py` proves the distinction between parallel-but-reverse and angled-but-lawful headings, nearest-edge selection, roadway footprint, changed-source rejection and duplicate-frame rejection. Three focused tests pass in `cpu-tests.log`.

Next CPU actions: author a source-reviewed one-way roadway/edge/context packet with responsible person, halt purpose and applicable Chapter exception review; build six CARLA-lazy exact construction/controller/camera bundles; retain original standing/parking histories and a saved finalizer; create canonical semantic stages, pinned offline/compatibility and saved-only proofs, and independent delivery/comparison audits. Physical motion and actual camera visibility remain later verification. C150041 remains partial. Frozen inputs/runtime/batch were preserved; no Git command was run.

## 2026-11-22 gate and return check after five-pair and parking work

Pinned `runtime.py preflight` passed; update check returned version 0 and no paused assignments. C125714's full 69-test suite passes with one diagnostic-root skip; C150041's three focused geometry tests and three repository tests pass. Exact static `worker_check.py --assignment ... --complete` exits 0 for both changed assignments. Both exact `--require-delivery-ready` checks exit 1 at `Preparation acceptance failed: partial/missing packages remain`, as does `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`. C125714 and C150041 remain truthful partials.

Read-only returned-file inspection covered 2,901 files; largest was 1,226,018 bytes. No file exceeded its size limit, failed UTF-8 decoding, contained trailing whitespace or conflict markers, or had a mismatched recorded test-log hash. No Git command was run.

## 2026-11-22 parking source custody continuation

`source_review.py` now checks retained original bytes and SHA-256 values for roadway, one-way direction, responsible-person/activity and Chapter-exception context. It rejects unsafe paths, missing reviewer/citation, a non-reviewed packet, inconsistent edge/direction geometry and an activity outside standing or parking. Its output feeds `parking_measurement.py` while retaining an unresolved legal judgment. The positive fixture is explicitly synthetic and does not establish public roadway, lawful direction or Chapter applicability.

`tests/test_source_review.py` exercises source tampering, path traversal, direction conflict and invalid activity, plus measurement from a validated source packet. Six focused tests pass in `cpu-tests.log`. Resume with genuine reviewed source bytes and a source-hashed packet before Native construction and pinned delivery proofs. C150041 remains partial; no Git command was run.

## 2026-11-22 source-bound pose planner continuation

`parking_pose.py` now constructs all six exact requested standing/parking poses from the reviewed packet's roadway edge, lawful direction and polygon. It chooses the one inward side, places the full four-corner vehicle footprint inside the roadway, preserves one center across comparisons, and varies only the requested orientation or heading. Its 30-degree angled and 2.5 m edge-offset targets are engineering fixture settings, not legal cutoffs. It rejects an unknown case, narrow roadway, absent edge segment and ambiguous inward side. `source_review.py` now also rejects a declared road edge that runs through the roadway polygon rather than bounding one side.

Eight focused tests pass, including an integrated synthetic source-packet-to-pose-to-measurement path, all six exact requested poses, reverse-heading versus parallel orientation, changed source bytes, internal edge and narrow-roadway negatives. The synthetic packet is only a protocol fixture. Exact Native route/controller/capture, original stopped-interval source history, semantic stages, pinned compatibility/saved proofs and sealed delivery/comparison audits remain worker-owned CPU work; C150041 stays partial. No Git command was run.

## 2026-11-22 final pose checkpoint checks

Pinned CPU `runtime.py preflight` passes after the pose changes. The C150041 focused suite passes eight tests. Exact static `worker_check.py --assignment testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver --complete` exits 0; its strict `--require-delivery-ready` form exits 1 with `Preparation acceptance failed: partial/missing packages remain`. Full-batch `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` also exits 1 at the same partial/missing-package gate. C125714's five-pair diagnostic suite passes 69 tests with one diagnostic-root skip, and its exact static check passes while strict readiness remains partial.

The final read-only returned-file scan covers 2,905 UTF-8 files, with a largest file of 1,226,018 bytes. It found zero size-limit, trailing-whitespace, conflict-marker or recorded test-log-hash issues. No Git command was run.

## 2026-11-22 source-bound scene and controller checkpoint

`parking_scene.py` now builds each exact case ID from a retained source packet and rejects a case whose requested standing/parking activity differs from the packet. It binds the five source hashes and packet SHA to a full-footprint spawn and target pose. Angled probes start on the lawful axis and request an angled final heading; reverse probes start in the reverse heading. A spawn outside the inspected roadway is rejected. `parking_control.py` supplies CARLA-lazy approach, braking and stationary-hold commands, and returns `needs_maneuver_review` rather than claiming a completed hold when the vehicle reaches the target with the wrong heading. Its controller tolerances are engineering values, not legal thresholds. The test's fake `VehicleControl` exercises the actual `apply_control` call shape.

The six source-bound scene drafts and controller behavior pass 11 focused CPU tests in `cpu-tests.log` (`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver/tests -v`; SHA-256 `1829d1db57dee5cac10bfc0b9bcc174259c8115463baaf7341192b1c4878faa9`). The positive source packets are deliberately synthetic protocol fixtures. They prove neither a real one-way roadway nor the physical feasibility of angled or reverse parking. `runtime.py preflight` and exact static `worker_check.py --assignment ... --complete` pass; exact strict readiness exits 1 because this assignment remains partial.

Resume CPU work by (1) retaining and reviewing genuine source bytes for the roadway edge/polygon, one-way direction, responsible person and standing/parking activities, and Chapter exceptions, then creating separate source-hashed packets for stand and park; (2) implementing Native actor spawn/step/capture integration with original body, heading, speed and control histories, saved finalization and case-specific media plans; (3) preparing canonical semantic proposals, exact offline/positive/negative compatibility and saved-only proofs, independent delivery/comparison audits, and a justified fallback if Native motion risk demands one. Do not mark ready until those proofs and the exact strict gate pass. No Git command was run.

## 2026-11-22 saved original-history finalizer checkpoint

`parking_finalizer.py` now consumes a SHA-256 verified original JSONL body/heading/speed/control history against a reviewed activity packet, measures every ordered frame through `parking_measurement.py`, and reports multi-frame engineering-stationary intervals. It rejects altered original bytes, an activity mismatch, absent stationary intervals and missing original control fields. It preserves the source packet and original history hashes, raw measured geometry, and unresolved legal judgment. The 0.15 m/s stationary speed is an engineering observation threshold, not a legal standing/parking definition. No synthetic fixture is represented as a real recording.

All 13 focused CPU tests pass with `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 is `dccb4ad536898c20d036e10b0e62b2733c8848069eda23e34fe519693077ea22`. Next implement the Native source writer and capture integration that can supply the specified JSONL history, and then the canonical stage proposals, pinned positive/negative compatibility and saved processing proofs, and independent delivery/comparison audits. Genuine reviewed stand/park source packets still need to be retained. Status remains partial. No Git command was run.

## 2026-11-22 Native-shaped original-frame serializer checkpoint

`parking_native_capture.py` now reads the actor bounding box, world transform, forward vector, velocity and applied control through lazy CARLA-shaped calls and serializes one frame of original body/heading/speed/control history. `tests/test_parking_native_capture.py` exercises each acquisition call with a CPU fake and rejects an invalid world frame or control outside Native range. The serializer can feed `parking_finalizer.py` through the caller's original JSONL file. It does not yet own the world tick, cameras, source file custody or physical maneuver.

The updated 15-test suite passes with `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 is `47fb17ecf05ea63d5d430ea3a65251108fa7dcea9fb1cf8b5f95ebf5aa784950`. Exact static `worker_check.py --assignment testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver --complete` exits 0. Exact strict readiness exits 1 at `Preparation acceptance failed: partial/missing packages remain`. Resume with genuine reviewed stand/park source packets, exact world/camera/capture runner, semantic proposals, pinned compatibility and saved processing proofs, and independent delivery/comparison audits. Status is partial; no Git command was run.

## 2026-11-22 four-pair measured comparison audit checkpoint

`parking_comparison_audit.py` now checks `park_parallelism`, `park_heading`, `stand_parallelism` and `stand_heading` against the two exact saved results for each pair. It requires identical reviewed source packet hashes, distinct original-history hashes, joined multi-frame stationary observations, full bodies in the reviewed roadway and fixed body placement. It then checks that the intended orientation or heading difference appears in measured original body geometry. It rejects a controller/request-only difference, changed source packet and changed fixed placement. Its separation and placement tolerances are engineering diagnostics, not statutory cutoffs. The CPU fixture is synthetic and no actual pair has been physically accepted.

The C150041 suite now passes 17 tests with `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 is `54204d202c44e8011855bfe9045680cf4b3a844b2242a1c6e536aa539c83dec0`. Exact static `worker_check.py --assignment testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver --complete` passes. Resume with the genuine reviewed source packets for each activity, Native world/camera and source writer integration, semantic proposals, pinned exact offline/compatibility and saved-processing proofs, and an independent delivery audit of source and media custody. Keep partial until the exact strict gate passes. No Git command was run.
