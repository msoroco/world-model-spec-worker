# testing__C104084__NRS-484B-603-1__motor_vehicle_driver

Status: partial exact-case construction. Three planned cases and two comparisons are proposed; no recording or physical acceptance is claimed.

Exact law: NRS 484B.603(1) — The fact that the speed of a vehicle is lower than the prescribed limits does not relieve a driver from the duty to decrease speed when approaching and crossing an intersection, when approaching and going around a curve, when approaching a hill crest, when traveling upon any narrow or winding highway, or when special hazards exist or may exist with respect to pedestrians or other traffic, or by reason of weather or other highway conditions, and speed must be decreased as may be necessary to avoid colliding with any person, vehicle or other conveyance on or entering a highway in compliance with legal requirements and the duty of all persons to use due care.
Assigned branch(es): Approaching a hill crest..
Cell: C104084 (hill_crest, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Current construction and proof

- `case-plan.json` now names exact `__early_decrease`, `__late_decrease`, and `__steady_approach` cases. `early_vs_late_precrest_decrease` changes the measured first-decrease station; `decrease_vs_steady_approach` changes the precrest speed history. The same original crest route, other-vehicle motion, highway/prescribed-limit context, cameras, duration, actor and initial speed are fixed in each comparison. These are physical probes; NRS 484B.603(1) supplies no universal deceleration threshold.
- `crest_controller.py` executes lazy station-based speed control through a caller-supplied CARLA-compatible control factory. It does not infer actual motion from commands. `crest_speed.py` requires original map grade and frame histories, measures the crest, precrest speed change and minimum same-frame body clearance, and rejects missing sources or postcrest-only samples.
- `comparison_audit.py` independently rejects changed or missing fixed source hashes, reused captures, missing original frame sources, and unrealized speed-profile differences. It makes no due-care or legal-necessity judgment.
- `.venv-cpu/bin/python runtime.py preflight` passed with the pinned CPU environment. `.venv-cpu/bin/python -m unittest discover -s work/testing__C104084__NRS-484B-603-1__motor_vehicle_driver/tests -v` passed 12 tests (`cpu-tests.log`). `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-603-1__motor_vehicle_driver --complete` passed (`assignment-check.log`). Exact strict command with `--require-delivery-ready` failed because this remains partial (`strict-gate.log`). Each log is SHA-bound in `result.json`.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Bind an original Native map with a real crest, source-measured approach station, ego and other-vehicle routes; exercise both route directions and actual grade/ray geometry with CPU fakes. Expand the case controller to the complete capture runner.
3. Implement the case-specific source-bound finalizer and diagnostic recipe, semantic proposals, offline/positive-negative compatibility, saved-only processing, delivery audit and risk-based fallbacks where a tested physical risk justifies them. Add manifest-level physical-risk assessment for every exact case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-603-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
