# testing__C111125__NRS-484B-307-5a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(5)(a) — Where the signal is a green straight-through arrow alone: Vehicular traffic facing the signal may proceed straight through, but must not turn right or left. Such vehicular traffic must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.
Assigned branch(es): Facing sole straight-through arrow.
Cell: C111125 (intersection, straight, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-5a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Current return: straight-arrow source guard and yield controller

The exact law permits straight travel when facing a sole green straight-through arrow, prohibits right/left turns, and requires yielding to vehicles and pedestrians lawfully within the intersection or adjacent crosswalk when the signal is exhibited. `case-plan.json` now identifies clear and occupied straight-through cases with a controlled participant-occupancy comparison, source observations, and the turn-prohibition scope question. No legal right-of-way label is inferred from body position alone.

`runner.py` implements an offline geometry check, an exact facing-head/per-frame sole-arrow guard, finite body-footprint overlap checks for the intersection and adjacent crosswalks, an independently sourced lawful-presence requirement, and a straight-only yield/hold controller. It deliberately rejects a generic CARLA green bulb, an extra illuminated indication, a changed head/frame, missing lawful-presence source, and entry after an uncleared yield guard. `scene.json` fixes the draft straight route and geometric regions. Five CPU tests pass in `cpu-tests.log`; `.venv-cpu/bin/python work/testing__C111125__NRS-484B-307-5a__motor_vehicle_driver/runner.py --check` passes. No Native capture is claimed; the runner currently raises on Native execution until head-source binding and capture are implemented.

Resume worker-owned CPU construction: implement source-verified arrow-head acquisition and a real CARLA straight-route runner, record all participant and signal histories at 20 Hz, build exact finalizer/measurement contract and semantic stages, add independent comparison/delivery audits, and run exact offline, compatibility, physical and saved-processing proofs. Review whether the turn prohibition can be covered within frozen straight-maneuver scope without changing the assignment. Keep partial until the CPU package is fully proved. A later Native run must verify actual arrow asset, visibility and motion; these later checks do not excuse missing CPU construction. The separate timer publishes the work; do not run Git.

`analysis.py` now reads four source-hashed original files: facing signal-head history, ego body/heading history, participant body/lawful-presence history and intersection/crosswalk geometry. It enforces frame/time joins, checks the exact sole arrow readback against the facing head and frame, measures first exhibition and ego entry, records occupied frames and ego positions past the stop line while occupancy continues, and retains heading change without a legal verdict. `tests/test_analysis.py` covers a clear-after-hold sequence, entry during occupancy, stale context hash, and an extra green indication at intersection entry. The combined suite now has nine passing CPU tests in `cpu-tests.log`. This analyzer is not yet wired into a complete Native construction or compatibility package; source-head acquisition remains worker implementation work.

`semantic_author.py` now writes the seven canonical proposal stage files under `proposals/`, with exact law text, two unresolved judgment phrases, source-bound observable requirements, grounded-cell bindings, and exact clear/occupied case IDs. The pinned `batch_pipeline.stages.validate` accepted batch relevance, cell relevance, template, both judgment proposals, bindings and cases. The sweep specs remain explicitly incomplete because Native arrow-source and physical occupancy ranges are not yet established; no judgment threshold or legal label was invented. Resume by wiring these proposed recording channels and contexts into a complete selected construction and executable Native capture, then run `semantic_delivery.validate` against its manifest and full compatibility proofs. The current return stays partial.
