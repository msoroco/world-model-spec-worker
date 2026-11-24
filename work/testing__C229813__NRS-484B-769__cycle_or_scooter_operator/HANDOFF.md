# testing__C229813__NRS-484B-769__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.769 — An operator of a bicycle, an electric bicycle or an electric scooter upon a roadway shall give all signals by hand and arm in the manner required by NRS 484B.420 [DEF-NRS-484B-420], except that the operator may give a signal for a right turn by extending his or her right hand and arm horizontally and to the right side of the bicycle, electric bicycle or electric scooter.
Assigned branch(es): alternative_right_turn_signal.
Cell: C229813 (road, right_turn, cyclist); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229813__NRS-484B-769__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 exact-case measurement checkpoint

The frozen accepted recording inventory is empty. The selected alternative is the right hand and arm extended horizontally on the right during a right turn by a covered bicycle, electric bicycle, or electric scooter operator on a roadway. The source witness is conditional. NRS 484B.420 is referenced by the exported law but its signaling-form details are not included in this assignment's frozen source. This checkpoint does not infer a conventional signal form, a signaling deadline, an independent duty to signal, or a legal posture cutoff.

`case-plan.json` now has nine exact cases: horizontal right arm, downward right arm, and bent right arm for each of bicycle, electric bicycle, and electric scooter. Three comparisons vary the requested right-arm posture within each operator kind while holding route, roadway, vehicle geometry, controller and capture contract fixed. These are intended physical probes, with no outcome claimed. Each case records the same concrete rider-arm actuation and camera-visibility risk; source trace and delivered pixels still need verification.

`signal_measurements.py` is a saved-source audit CLI. It binds the exact case, receipt, original context and trace SHA256s; rejects diagnostic fixtures and invalid operator classifications; checks sourced highway/roadway/shoulder context, a clockwise/right-turn route, 20 Hz frame ordering, and required right-arm joints. It reports per-frame roadway occupancy and wrist/elbow lateral, forward and vertical components in the rider heading frame. It leaves legal signal form, timing, and physical pixel visibility unresolved. `tests/test_signal_measurements.py` exercises a positive horizontal right-arm source and eight invalid or contrast conditions, including downward/left-side posture, shoulder contact, a non-right route, missing joints, source mutation and diagnostic refusal.

Checks: `.venv-cpu/bin/python runtime.py preflight` exited 0 (`preflight.log`); `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229813__NRS-484B-769__cycle_or_scooter_operator/tests -v` exited 0 with 9 tests (`cpu-signal-tests.log`). These are fixture/software checks, not physical evidence.

Next CPU construction is an actual source-bound Native actor/arm controller and three covered kind configurations, exact case bundles and manifest, four-camera acquisition and source-hashed diagnostics, executable finalizers and semantic proposals, positive/negative offline compatibility, saved-only processing, and independent delivery/comparison audits. Then run the scoped strict gate. CARLA motion and actual rider-arm visibility remain later physical checks; they do not excuse the pending CPU package.

Scoped static check exited 0 with `static_checks_passed: true` (`assignment-check.log`). Exact scoped strict check exited 1 because `result.json.status` remains truthful `partial` (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). No delivery-ready claim is made.
