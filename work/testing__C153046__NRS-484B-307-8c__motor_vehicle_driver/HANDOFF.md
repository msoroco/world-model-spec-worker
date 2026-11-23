# testing__C153046__NRS-484B-307-8c__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(8)(c) — Where the signal is a steady red signal alone: After complying with the requirement to stop, vehicular traffic facing such a signal and situated on the extreme right of the highway may proceed into the intersection for a right turn only when the intersecting highway is two-directional or one-way to the right, or vehicular traffic facing such a signal and situated on the extreme left of a one-way highway may proceed into the intersection for a left turn only when the intersecting highway is one-way to the left, but must yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection.
Assigned branch(es): one_way_left_turn.
Cell: C153046 (one_way_to_one_way_intersection, left_turn, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C153046__NRS-484B-307-8c__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-22 exact red-left-turn CPU construction start

`build_case_plan.py` expanded the frozen `one_way_left_turn` branch into eight exact draft attempts and five controlled comparisons: antecedent stop, extreme-left approach lane, receiving one-way direction, pedestrian response and signal-directed traffic response. `case-plan.json` now maps eight law observations to intended source or saved measurement and records that all site facts and realized outcomes remain pending. No numeric statutory cutoff or legal verdict was invented. The requested probe differences are not claimed as realized.

`red_left_turn_controller.py` is a CARLA-lazy engineering motion request controller. It requests approach, a sampled full stop before the sourced boundary, yielding while pedestrian or traffic conflicts are present, and a left turn only for the observed steady-red-alone signal. It also supports the exact rolling and advance request probes without labeling their outcomes. `cpu-tests.log` records six passing CPU tests for stop/turn ordering, pedestrian and traffic waits, rolling/advance requests, invalid time/source input, and five pair isolations. The controller does not establish a genuine signal, one-way lane, stop hierarchy, Native route or physical yielding.

Resume by binding reviewed OpenDRIVE and lane direction, official signal and stop boundary, and source-reviewed conflict paths to exact scene geometry; then implement the Native runner/capture, source-bound finalizer, semantic proposals and exact positive/negative pinned offline/compatibility and independent audits. Keep `result.json` partial until those proofs and the strict delivery gate pass. No Git command was run.

### Proposed source-bound site geometry guard

`source_bound_scene.py` now checks a proposed site's exact retained OpenDRIVE, signal-authority, approach-lane, receiving-lane and stop-boundary source hashes and citations. It computes the extreme-left lane from source coordinates and checks that approach and receiving directions form a left turn. It selects the inner-lane and two-way-receiving draft variants from their declared packet facts; it does not assert that those facts are true. The two new CPU tests use labeled synthetic text fixtures and reject changed map bytes, a falsely named extreme-left lane, a rightward receiving direction and a one-way packet for the two-way probe. The full C153046 suite now passes eight tests.

Resume with reviewed Native OpenDRIVE and documentary signal/lane/stop sources, then bind exact route waypoints and original frame histories to this site packet. The validator checks custody and geometry consistency only; source authority and physical realization remain open. Current `result.json` retains partial status. No Git command was run.
