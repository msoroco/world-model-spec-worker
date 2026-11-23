# testing__C111260__NRS-484B-270-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(1) — The driver of a motor vehicle shall not intentionally interfere with the movement of a person lawfully riding a bicycle, an electric bicycle or an electric scooter.
Assigned branch(es): Bicycle rider.
Cell: C111260 (intersection, travel, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Controlled bicycle encounter checkpoint

The exact bicycle-rider branch now has two planned case IDs, `testing__C111260__NRS-484B-270-1__motor_vehicle_driver__maintain_clearance` and `testing__C111260__NRS-484B-270-1__motor_vehicle_driver__cross_rider_path`, in `case-plan.json`, joined by `bicycle_encounter_behavior`. The difference is an ego controller command; map, routes, rider classification, cameras, duration and bicycle rider are fixed. This compares observable behavior without asserting lawful riding, intent or interference from geometry. The exact law also names electric bicycle and electric scooter riders; those alternatives remain explicitly pending CPU construction and source definitions.

`bicycle_encounter.py` source-gates the Native map, routes, bicycle classification and rider rules packets; proves crossing geometry; spawns the motor vehicle and bicycle through an injected CARLA-like API with cleanup after a partial spawn; and measures original continuous frame, blueprint, visual-rider and controller-command histories. `encounter_control.py` supplies both behavior commands. `comparison_audit.py` independently rejects missing original sources, changed fixed conditions and asserted legal verdicts. The assigned witness requires a human-powered bicycle satisfying NRS 484A.025, a distinct motor vehicle, rider conduct facts and unresolved legal terms; the implementation preserves those distinctions.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-1__motor_vehicle_driver/tests -v` passed six tests. Log: `cpu-tests.log` (SHA256: 118366bd7ecc0c739d882b356a747e56194b1fb29eac8847c7a09f8727fb4058). Tests cover positive construction/measurement and negative source hash, source packet, geometry, failed spawn, comparison fixed condition, and legal-verdict branches. The source packets themselves must still be constructed from a surveyed real Native cell; these tests use textual mocks and are not physical evidence.

Remaining CPU work: build source-bound Native survey packets and all three rider modality variants; finish exact runner/config/construction, measurement finalizer, canonical semantic proposals, delivery audit, case-specific positive/negative compatibility, saved-only processing, manifest and risk-based candidate checks. Physical rider render, actual motion and four-view capture remain later GPU checks. Current status stays partial.
