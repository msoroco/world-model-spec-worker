# testing__C158196__NRS-484B-257-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(1) — Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Yield sign; neither stop line nor crosswalk; nearest-view location..
Cell: C158196 (one_way_to_two_way_intersection, travel, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 4. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 4 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 source-gated nearest-view construction checkpoint

The full law and source-hashed witness require a proper yield sign, no stop line or near-side crosswalk (including a sidewalk-derived one), a through highway, and no actual officer or signal control. C158196 is cataloged with traffic_light control; the `active_signal_exception` exact case retains that condition as a separate applicability probe. The three yield cases require Native readback showing the signal does not govern. These are proposed scenes, not observed physical facts. The two frozen accepted demo-test records expose only 900-frame metadata and no original trace/video bytes in this export, so they are not treated as proof of the nearest-view branch or full-test coverage.

`case-plan.json` now names four exact cases (`nearest_view_hold`, `nearest_view_continue`, `nearest_view_clear`, `active_signal_exception`) and three controlled comparisons (`nearest_view_conflict_response`, `nearest_view_traffic_occupancy`, `governing_signal_exception`) with explicit fixed conditions and declared differences. `construction.py` validates Native cell/layout, connected route, through-highway, sign/signal/officer readback, absence of both crosswalk types and stop line, and source hashes before issuing an engineering control. It isolates an observed occupancy response without assigning a legal cutoff. `nearest_view.py` requires original 20 Hz frames and source packet hashes; it measures first view before entry, approach minimum speed, through-vehicle center at view, and occupancy across the crossing interval. Immediate hazard and right of way stay unresolved judgments. The comparison function rejects changes to undeclared context. This is a source interface and CPU construction draft; no Native scene has yet been executed.

Focused 12-test suite: `.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-1__motor_vehicle_driver/tests -v` passed; `cpu-tests.log` SHA-256 `29d310d066ec46e9abdf2082a13b1b83f26ca32605c24b2258dd1855fec04ef3`. `.venv-cpu/bin/python runtime.py preflight` passed (`.runtime-work/c158196-preflight.log`). Exact static check passed (`.runtime-work/c158196-static.log`); exact strict check failed with `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/c158196-strict.log`). No ready claim.

Next CPU work: source-bind a real Native site survey and yield/sign control state; implement the exact CARLA-lazy runner, actor/camera acquisition and sealed original tick capture; author selected requirement measurement contracts and canonical semantic proposals; run pinned offline, positive/negative compatibility and saved-only processing for every exact case; implement and test independent delivery, pixel and controlled comparison audits. Then rerun exact strict gate. Physical motion, pixels and legal judgment remain unverified. No Git command was run.

## 2026-11-23 pinned offline and original-source interface proofs

`build_offline_draft.py` embeds the frozen assignment bytes, exact selected config, `construction.py`, `nearest_view.py`, and two embedded checks into each of four `construction-*.json` bundles. Each runner refuses Native capture because its site is explicitly synthetic. `execution-manifest.draft.json` binds the four construction SHA-256 values. All four exact `runtime.py offline` checks passed (`cpu-offline-*.log`); these checks validate materialization and embedded tests only.

`nearest_view.py` now verifies each source path and SHA-256 against bytes inside the saved attempt before measuring original ticks. `prove_source_analysis.py` generated an explicitly synthetic seven-frame, 20 Hz packet under `.runtime-work/c158196-source-analysis`, ran the CLI positive path, removed the view-ray source, and observed the expected `view_raycast source bytes missing` rejection. See `cpu-source-proof.log`, `cpu-source-positive.log`, and `cpu-source-negative.log`. This is a source-binding CPU proof, not Native/camera physical evidence or the pinned compatibility proof.

The focused suite now passes 14 tests (`cpu-tests.log`, SHA-256 `76a253a051214f8c325f10efd9835eae9e9e96962a3b75ab592a82a84766d410`). `result.json` lists seven passing commands with hashes. Next: replace diagnostic site declarations with reviewed Native map, sign/signal, crosswalk, viewpoint and highway packet bytes; implement actual lazy CARLA actor/camera acquisition and sealed 900-frame capture; write selected-requirement contracts, semantic proposals and case-specific fixture sources; run the pinned positive/negative compatibility, saved-only processing, delivery and comparison audits. Keep partial until exact strict gate passes. No Git command was run.

## 2026-11-23 original Native body and raycast derivation

`native_observation.py` now derives the original ego front station, ego speed, through-vehicle center station, intersection occupancy, and view state from supplied four-corner Native body geometry, velocity, snapshot and a raycast whose endpoints must lie in the corresponding observed bodies. It rejects signal/officer control in this yield-branch adapter. Three new negative/positive tests pass; the focused suite totals 17 tests. This adapter is embedded in all four exact diagnostic constructions and each pinned offline check was rerun after the code change. The bundles remain diagnostic-only and refuse CARLA capture.

Exact outputs: `cpu-tests.log` SHA-256 `2d3b7632cff9fe9a60906a58d76666d2332138ae90853f1985be62e94a7cb695`; four current offline logs listed with hashes in `result.json`. The original Native frame source and saved video path still need binding. The active-signal exception case deliberately does not call the yield-branch adapter: it needs a separate sourced applicability measurement, not a false yield event. No Git command was run.

## 2026-11-23 source-bound saved comparison audit

`saved_comparison.py` now reopens both saved nearest-view packets and every declared original source before measuring linked cases. It enforces exact case identity, fixed context, the observed hold versus continuation response with occupied traffic in both cases, and the observed occupied versus clear crossing contrast under the same continuation policy. It returns measurements with unresolved legal judgment. A source hash mismatch, undeclared fixed-context change, absent occupancy contrast, or absent hold response fails the audit. This covers `nearest_view_conflict_response` and `nearest_view_traffic_occupancy`; the active-signal applicability comparison still requires its distinct measurement path.

`prove_saved_comparison.py` retains a synthetic CLI positive proof and a tampered `view_raycast` source rejection in `cpu-comparison-positive.log`, `cpu-comparison-negative.log`, and `cpu-comparison-proof.log`; synthetic packets are software tests, not Native evidence. The focused suite passes 20 tests, including three new saved comparison tests; `cpu-tests.log` and `result.json` contain current command hashes. Exact assignment static check passes in `cpu-static-nov23.log`. Exact strict check fails in `cpu-strict-nov23.log` because status is truthfully partial. Next CPU work remains the real Native site and four-camera acquisition, canonical semantic proposals, selected-requirement contracts, pinned compatibility, saved-only processing, active-signal comparison, and delivery/pixel audits. No Git command was run.
