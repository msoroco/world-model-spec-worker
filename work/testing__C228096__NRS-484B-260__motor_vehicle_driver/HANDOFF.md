# testing__C228096__NRS-484B-260__motor_vehicle_driver

Status: partial CPU construction. Nine cases and six comparisons are selected; the Native delivery package remains in progress.

## 2026-11-27 selected construction checkpoint

Status: partial CPU construction. `case-plan.json` now selects nine exact cases and six controlled comparisons: `enter_right_wait`, `enter_right_intrude`, `enter_left_wait`, `enter_left_intrude`, `cross_both_wait`, `cross_both_intrude`, `enter_both_wait`, `enter_both_yield_one`, and `enter_no_approach`. Each ID is prefixed by this assignment ID. The comparisons are `right_wait_vs_intrude`, `left_wait_vs_intrude`, `cross_wait_vs_intrude`, `both_wait_vs_yield_one`, `right_approach_vs_none`, and `entry_vs_crossing`. No accepted original evidence is listed in the frozen evidence inventory.

`private_way_site.py` verifies six original source hashes including the Native OpenDRIVE map, and reviewed private ownership, access, highway designation, route connection, both maneuver paths and both approach directions. It rejects missing or altered sources, absent private status and an approach oriented away from the connection. `private_way_construction.py` produces nine exact 900-frame four-camera targets and a bounded spawn adjustment that keeps the case, ego route and requested control policy fixed. `private_way_motion.py` checks a sealed 20 Hz ego and complete highway-actor history without a legal verdict. `native_acquisition.py` binds the reviewed site/map, readback of every actor, four original PNG streams and cleanup into one original attempt. An 11-test synthetic fixture exercises a nine-frame acquisition and owner cleanup; it does not establish full video decoding, physical realization or legal compliance.

`native_operator.py` is a lazy CARLA implementation: it checks the loaded OpenDRIVE hash, reviewed vehicle spawns and ego-local camera mounts, enables a 20 Hz synchronous world, controls ego and highway actors along reviewed through-connection routes, reads actual body vertices/velocity/brake and four camera pixels, rejects unmanaged highway vehicles in the reviewed highway polygon, encodes four FFV1 videos and a four-view composite, and restores the world after cleanup. Its real CARLA branch has not run on this CPU worker. `runner.py` is the operator entrypoint. `build_measurements.py` writes nine source-bound contract drafts, each requiring the sealed original motion and relevant reviewed site or actor sources. These drafts await the saved finalizer and runtime compatibility proof.

Next CPU actions for this assignment: connect the Native runner output to the runtime attempt schema and implement a case-specific saved finalizer; bind each exact construction and justified fallback into offline and positive/negative compatibility receipts; add semantic proposals, saved-only processing, physical completion lifecycle proof, independent original delivery and comparison audits; run the exact strict assignment gate. The entry/crossing control requests are engineering probes only. Original ownership, designation, feasible connection, actor motion, pixel visibility and statutory yielding need source-backed local review.

Exact law: NRS 484B.260 — The driver of a vehicle about to enter or cross a highway from a private way shall yield the right-of-way to all vehicles approaching on such highway.
Assigned branch(es): enter_highway_from_private_way_on_general_road_layout.
Cell: C228096 (road, enter_road, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__NRS-484B-260__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
