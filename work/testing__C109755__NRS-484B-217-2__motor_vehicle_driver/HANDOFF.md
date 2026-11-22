# testing__C109755__NRS-484B-217-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.217(2); with 484B.217(3), 484B.217(4) — Except as otherwise provided in subsections 3 and 4, a driver shall not drive on the left side of the highway within such zone or drive across or on the left side of any pavement striping designed to mark such zone throughout its length. A driver may drive across a pavement striping marking such zone to an adjoining highway if the driver has first given the appropriate turn signal and there will be no impediment to oncoming or following traffic. Except where otherwise provided, a driver may drive across a pavement striping marking such a zone to make a left-hand turn if the driver has first given the appropriate turn signal in compliance with NRS 484B.413 [NRS-484B-413-2], if it is safe and if it would not be an impediment to oncoming or following traffic.
Assigned branch(es): left-hand-turn crossing.
Cell: C109755 (intersection, left_turn, pavement_striping); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109755__NRS-484B-217-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Construction and proof checkpoint

Exact cases: `testing__C109755__NRS-484B-217-2__motor_vehicle_driver__signaled_left_turn` and `testing__C109755__NRS-484B-217-2__motor_vehicle_driver__unsignaled_left_turn`. `case-plan.json` links them in comparison `turn_signal_before_stripe`: the connected route, stripe, actors, traffic policies, cameras and duration stay fixed; observed left signal is the deliberate difference. `runner.py` computes a route crossing the center striping and checks signal station order; its `require_marking` rejects a map without a solid lane marking. CPU tests exercise actual three-actor spawn calls, including opposing heading, and missing-marking rejection. Both exact `runtime.py offline` runs pass; logs: `proof-signaled.log`, `proof-unsignaled.log`. `analysis.py` reads SHA-bound original turn history and zone context, detects observed crossing and signal timing, and reports traffic gaps without a legal safety cutoff. `comparison_audit.py` rejects missing source-bound measurements and changed fixed conditions. Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C109755__NRS-484B-217-2__motor_vehicle_driver/tests` (10 tests; `cpu-tests.log`).

The current Native path is unfinished. A solid lane marking alone does not prove the statutory zone's extent or exceptions under NRS 484B.217(3),(4); those sources and actual map applicability must be checked. The CPU fixtures are synthetic and do not prove safe turning or lack of impediment. Candidate risk is physical because connected geometry and actual zone striping may fail; no tested alternate map/candidate is available, so this remains partial.

Next CPU actions: implement Native controller and synchronized four-camera capture with pinned `PipelineCapture`, record original body/stripe/signal/traffic histories and acquisition hashes, bind `analysis.py` into saved processing, implement source-bound positive/negative compatibility and independent delivery audit, add canonical semantic proposals, review subsections 3 and 4 and exact statutory alternatives, and construct/test any justified fallback. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109755__NRS-484B-217-2__motor_vehicle_driver --complete --require-delivery-ready` after these CPU deliverables.
`delivery_audit.py` now checks the sealed original-source hashes, Native exit and owner release receipts, physical completion booleans, frame/time joins, saved result binding, and the pinned media decode receipt through a lazy verifier. Its CPU tests include missing-source and failed-completion rejection; total 13 tests pass. These fixture tests do not substitute for an actual decoded video or body-visible CARLA capture. The final exact offline proof logs are `proof-signaled.log` and `proof-unsignaled.log` after including this audit.

Final checkpoint gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C109755__NRS-484B-217-2__motor_vehicle_driver --complete` passes. `.venv-cpu/bin/python worker_check.py --complete` passes static checks for all 242 partial packages. `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain`; retained log: `.runtime-work/strict-check-final.log`. The failing readiness gate reflects unfinished CPU deliverables listed above, not a missing CPU dependency or a claim of GPU readiness.
