# testing__C202480__NRS-484B-560-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.560(3) — When stopping is required at a railroad crossing the driver shall keep as far to the right of the highway as possible and shall not form two lanes of traffic unless the highway is marked for four or more lanes of traffic.
Assigned branch(es): Two-lanes prohibition with its marked-four-or-more-lanes qualification; retain the independent right-side duty..
Cell: C202480 (rail_crossing, cross_railway, stop_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C202480__NRS-484B-560-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 branch plan and first audit implementation

`case-plan.json` now proposes five exact delivery cases and four controlled comparisons: two marked lanes with one or two queues, four marked lanes with two queues, and rightmost versus left-of-feasible subject placement. These are plans; no physical crossing or marked lane construction is claimed. `crossing_branch_audit.py` requires six source-hashed original evidence files before classifying the two-queue context, total marked highway lane qualification and independent right-side evidence. It never returns a legal conclusion. `cpu-branch-audit.log` passes three tests including source removal and unreviewed stop/arrangement rejection.

Next: build source-grounded crossing, sign/signal authority, marked lane geometry and independently positioned vehicle queues; implement per-frame finalizer and audited comparisons, then run offline and compatibility proofs. Keep stop authority and highway boundaries unresolved until supported by reviewed source files.

Focused `.venv-cpu/bin/python worker_check.py --assignment testing__C202480__NRS-484B-560-3__motor_vehicle_driver --complete` passed; retained in `cpu-static-check.log`. Strict delivery readiness is still unclaimed.

## 2026-11-23 source-bound Native and saved processing checkpoint

`native_scene.py` checks a source-hashed site packet against original OpenDRIVE, crossing authority, lane-marking, highway-boundary, right-side, and camera-pose documents before spawning the ego and optional companion in either approach direction. `native_control.py` uses live actor position and speed. `native_camera.py` captures four original BGRA views; `native_capture.py` joins exactly 900 rendered synchronous 20 Hz frames to actor motion and camera hashes. `runner.py` restores the Native world and retains the site packet and source bytes beside a closed attempt. `native_media.py` validates raw pixels and encodes FFV1; `saved_pipeline.py` gates postcapture work on successful Native status and restoration. `saved_measurement.py` checks retained hashes, four videos, cadence, motion and a contiguous one-second stop observation. It leaves legal judgment unresolved.

The diagnostic CPU suite passes 25 tests (`cpu-source-finalizer-tests.log`), including all five cases in both directions with fake Native actors, camera joins, missing/changed source rejection, cleanup, saved stationary and failure measurements, and postcapture ordering. The saved observation alone leaves `maneuver_completed` false. These tests prove implementation behavior on synthetic diagnostic sources, not an actual reviewed crossing or physical acceptance. Pinned `runtime.py preflight` and focused `worker_check.py --assignment ... --complete` pass. The result stays **partial**.

Next worker-owned CPU work: choose and review a real crossing site packet with authority, total highway marking and right-side boundary evidence; complete the case manifest and physical-risk assessment; produce semantic proposals and exact offline/compatibility receipts; implement independent delivery and comparison audits, including visual source review. Then run exact strict readiness and full batch gates. No real Native recording or legal determination is claimed here.

## 2026-11-23 original footprint and independent geometry continuation

Native capture now retains each actor's bounding-box half extents, heading and stable actor ID with its position/velocity. The saved finalizer rejects missing or invalid footprint data, changed actor IDs, wrong-way headings and vehicles outside the reviewed highway bounds. It measures the stopped ego's lateral offset from the source-bound rightmost feasible slot and counts frames where two stopped vehicle footprints are laterally separate and longitudinally overlapping before the rail. These are engineering observations, not legal cutoffs or physical completion claims. `geometry_audit.py` independently recomputes the right-side and two-queue observations from the original trace, verifies source hashes, and rejects an inflated saved result. `saved_pipeline.py` runs it after the saved finalizer and retains `geometry-audit.json` beside the attempt.

The updated diagnostic suite passes 29 tests (`cpu-geometry-audit-tests.log`), including a two-queue overlap/separation comparison and an out-of-highway footprint rejection. Pinned CPU preflight and focused assignment static check pass. This is still **partial**: the geometry audit does not perform canonical full video decode, visual review, law determination or the required independent comparison audit. Complete the remaining worker-owned CPU package and exact readiness proofs before promotion.

## 2026-11-23 four-pair comparison isolation checkpoint

The four planned comparisons now have exact `comparison_id` values in `case-plan.json`: `two_marked_queue_arrangement`, `marked_lane_qualification`, `four_marked_right_side`, and `two_marked_right_side`. `comparison_audit.py` calls the independent original-geometry audit for each paired attempt, checks exact case order and source-bound crossing authority, approach, camera configuration and fixed road geometry, then verifies the intended measured queue, lane-count or lateral-position contrast. The lane-count comparison permits a different OpenDRIVE source while requiring the same crossing authority and stop geometry. Its 32-test diagnostic suite (`cpu-comparison-audit-tests.log`) covers all four pairs and rejects absent queue contrast or changed fixed OpenDRIVE. The audit is executable after original captures; the synthetic fixtures do not establish real geometry or law compliance.

Pinned CPU preflight and focused `worker_check.py --assignment testing__C202480__NRS-484B-560-3__motor_vehicle_driver --complete` pass. C202480 remains **partial** pending source-reviewed real site selection, full semantic proposals, exact offline/positive-negative compatibility receipts and canonical full-video delivery audit. The full strict batch gate has not passed.
