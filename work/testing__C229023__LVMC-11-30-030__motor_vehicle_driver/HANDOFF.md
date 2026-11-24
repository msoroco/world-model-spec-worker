# testing__C229023__LVMC-11-30-030__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.030 — Whenever any vehicle is stopped at a marked crosswalk or at any unmarked crosswalk at an intersection to permit a pedestrian to cross the roadway, the driver of any other vehicle approaching from the rear shall not overtake and pass such stopped vehicle.
Assigned branch(es): Unmarked crosswalk at an intersection.
Cell: C229023 (road, overtake, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__LVMC-11-30-030__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 exact-case and saved-source measurement checkpoint

The exact LVMC 11.30.030 text covers a vehicle stopped at a marked crosswalk or an unmarked crosswalk at an intersection to permit a pedestrian to cross, and the rear-approaching driver overtaking and passing it. The frozen witness selects the conditional unmarked branch in broad road cell C229023. `case-plan.json` now preserves six exact targets: unmarked/marked pass and wait, plus unmarked pass and wait with a different lead-stop purpose. Five comparisons isolate pass behavior, crossing kind and stop purpose. No frozen accepted recording exists for this assignment; these are planned targets, not accepted evidence or verdicts. The unmarked branch needs reviewed opposite sidewalk lateral-line and curb/traveled-edge geometry, and divided-roadway intersection rules when applicable.

`crosswalk_measurements.py` reopens hash-sealed original context and trace bytes and rejects diagnostic receipts. It requires an actual road intersection, marked-source or unmarked sidewalk/curb source references, a separate stopped-purpose source, three actor identities, a unit road axis, 20 Hz ordered frames, and eight original world-space body vertices per vehicle. It records sampled rear approach only when ego front is behind lead rear and sampled full pass only when ego rear is ahead of lead front. It also reports stopped lead frames and pedestrian-in-polygon frames separately. It does not infer purpose from the pedestrian motion, establish legal crosswalk applicability, or render a legal judgment. The CLI writes replayable JSON only after successful measurement.

Eight focused CPU tests passed in `cpu-crosswalk-tests.log`, including CLI replay and negative missing geometry, purpose source, marked source, changed bytes, dropped frames, missing vertices and diagnostic provenance. `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__LVMC-11-30-030__motor_vehicle_driver --complete` passed in `assignment-check.log`; exact scoped strict failed because status remains partial in `strict-gate.log`. Proof hashes are current in `result.json`. Next CPU work: source-reviewed Native intersection/crosswalk packet and six executable scene bundles; actor controllers and synchronized four-camera acquisition; case finalization, semantic proposals, exact offline and positive/negative compatibility, saved-only delivery and independent media/comparison audits. Actual physical actor motion and camera visibility remain unverified.
