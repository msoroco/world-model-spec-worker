# testing__C227890__NRS-484B-410__motor_vehicle_driver

Status: ready for Native acquisition. The exact scoped CPU strict delivery gate passed after the final bound changes; six cases and five controlled comparisons are queued for operator review.

Exact law: NRS 484B.410 — A person, except when stopping, standing or parking where no parking is permitted, shall not start a vehicle which is stopped, standing or parked on a highway nor enter upon a highway unless and until such movement can be made with safety.
Assigned branch(es): Start from a parked position on a highway.
Cell: C227890 (road, depart_parked, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU readiness and operator handoff

The exact scoped gate passed with `--assignment testing__C227890__NRS-484B-410__motor_vehicle_driver --complete --require-delivery-ready` and `static_checks_passed: true`. Lead independently repeated the scoped gate and integrated six cases and five comparisons from `queue-proposal.json`. The `result.json` status is `ready` with `delivery_prepared` readiness kind. Native source review, acquisition, motion/video checks, and legal review remain operator acceptance work.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 source-grounded construction

The exact selected witness is an ordinary motor-vehicle driver's departure from a permitted parked position within a publicly dedicated highway. Six exact cases are now planned: `rear_wait`, `rear_intrude`, `rear_clear`, `opposing_wait`, `opposing_intrude`, and `opposing_nonconflict`. The five pairs in `case-plan.json` isolate departure timing, approach presence, route crossing, and approach direction while retaining the same permitted parking context. There are no accepted original recordings in the frozen evidence inventory and no judgment-range entry for this exact law and actor. The prohibited-parking exception, stopped and standing alternatives, and entry onto a highway are outside this frozen parked-departure witness; no safety distance or time is treated as a legal cutoff.

`parked_construction.py` requires source-hashed map, public highway boundaries, dedication, public use, parking permission at capture time, ordinary vehicle and approach-route sources. It verifies the parked pose lies inside the reviewed permitted bay and departure/approach routes lie inside the reviewed highway. Each primary and fallback targets the same case. The fallback moves the parked pose and departure entry/exit within the same reviewed permitted bay only when the primary cannot realize the original departure or camera coverage. `runner.py`, `native_acquisition.py`, `finalize_native.py`, `parked_activity.py`, and `analysis.py` implement the lazy CARLA handoff, 900 original 20 Hz frame capture, four original camera streams, map/actor readback, FFV1 lossless original camera encoding, source-sealed original activity, saved-only analysis and unreviewed legal status. Native physical realization and legal parking/safety review remain unverified.

`build_semantic.py` writes relevance, exact-law template, judgment-observable, cell binding, and expanded exact-case proposals. `build_constructions.py`, `build_measurements.py`, `build_manifest.py`, and `build_diagnostic.py` bind selected cases to exact source-hashed constructions, measurement contracts and nine-frame synthetic diagnostics. All twelve primary/fallback `runtime.py offline` checks passed. The twelve pinned `runtime.py compatibility` checks passed with actual analysis, Lean adapter, four-view decode, selected measurements and missing original activity rejection. These are software diagnostics, not original physical evidence. `physical_probe.py` and `run_physical.py` prove the three evidence states and Native exit/owner-release sequencing without claiming actual motion. `delivery_audit.py` and `comparison_audit.py` provide independent original-source and controlled-difference audits; their CPU positive/negative receipts passed for six delivery and five comparison cases.

Proof commands use `PYTHONDONTWRITEBYTECODE=1` and `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/...` and place all scratch, temporary bundles and media under `.runtime-work/`. The exact scoped strict gate passed, and the lead integrated `queue-proposal.json` into the shared queue. Actual CARLA motion, public-highway/parking context, route realization, camera visibility, and independent legal review remain for local operator acceptance.
