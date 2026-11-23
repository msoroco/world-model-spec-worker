# testing__C153046__NRS-484B-307-8a__motor_vehicle_driver

Status: partial construction draft. Eight requested cases and five controlled comparisons are planned; no recording or physical outcome is claimed.

Exact law: NRS 484B.307(8)(a); with 484B.307(8)(c) — Where the signal is a steady red signal alone: Vehicular traffic facing the signal must stop before entering the crosswalk on the nearest side of the intersection where the sign or pavement marking indicates where the stop must be made, or in the absence of any such crosswalk, sign or marking, then before entering the intersection, and, except as otherwise provided in paragraphs (c) and (d) [(c) is appended below, NRS-484B-307-8d], must remain stopped or standing until the green signal is shown. After complying with the requirement to stop, vehicular traffic facing such a signal and situated on the extreme right of the highway may proceed into the intersection for a right turn only when the intersecting highway is two-directional or one-way to the right, or vehicular traffic facing such a signal and situated on the extreme left of a one-way highway may proceed into the intersection for a left turn only when the intersecting highway is one-way to the left, but must yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection.
Assigned branch(es): one_way_left_turn_after_stop.
Cell: C153046 (one_way_to_one_way_intersection, left_turn, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C153046__NRS-484B-307-8a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

- `build_case_plan.py` expanded the one-way left-turn-after-stop branch to eight requested attempts and five controlled comparisons in `case-plan.json`: stopping, extreme-left position, receiving direction, pedestrian yield and traffic yield. The inner-lane and two-way receiving variants are applicability probes; their use within the frozen cell needs source review. Zero accepted recordings are inventoried. No judgment range is assigned to this law/actor.
- `red_left_measurement.py` requires byte-hashed OpenDRIVE, official signal, one-way routes and stop-reference sources before measuring original 20 Hz Native frames. It measures full-body stop-reference entry, pre-entry zero-speed samples and signal-directed conflict at entry without a legal verdict. The fixture is synthetic and proves only software behavior.
- `native_setup.py` lazily spawns source-cited actors, verifies upstream extreme-left heading and exact official signal actor, and rolls back owned spawns on failure. `comparison_audit.py` rejects changed site/stop reference, missing original frame proof, wrong cases and reused traces.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C153046__NRS-484B-307-8a__motor_vehicle_driver/tests -v` passed 16 tests; result.json records the exact log SHA. `.venv-cpu/bin/python worker_check.py --assignment testing__C153046__NRS-484B-307-8a__motor_vehicle_driver --complete` passed static checks. The same command with `--require-delivery-ready` failed at `Preparation acceptance failed: partial/missing packages remain`, as expected for this partial result. Logs are retained locally.
- Next CPU work: bind a real reviewed C153046 Native site packet and exact stop-reference hierarchy; implement source-gated controllers and per-case construction for all eight variants; complete semantic proposals, exact manifest and diagnostic recipes; run each offline and positive/negative compatibility proof; implement saved-only finalization and independent sealed delivery audit. Assess physical risk and candidate fallbacks per exact case. Keep original inputs and runtime frozen.
