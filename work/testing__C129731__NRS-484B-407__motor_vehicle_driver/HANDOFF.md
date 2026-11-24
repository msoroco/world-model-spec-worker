# testing__C129731__NRS-484B-407__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.407 — A vehicle shall not be turned so as to proceed in the opposite direction upon any curve, or upon the approach to or near the crest of a grade, where such vehicle cannot be seen by the driver of any other vehicle approaching from either direction within 500 feet.
Assigned branch(es): Mountain-road curve with documented visibility circumstances..
Cell: C129731 (mountain_road, u_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 10. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C129731__NRS-484B-407__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-24 accepted-reuse and 500-foot sight checkpoint

The frozen inventory names ten accepted recordings shared by demo-test/full-test and seven authored comparisons. The exported files contain their metadata and review descriptions, but not the original traces or videos. `case-plan.json.accepted_reuse_candidates` retains each exact recording ID with `new_recording_planned: false`; `accepted_comparisons_pending_original_review` retains all seven pairs. The ordinary `cases` and `comparisons` lists stay empty because source review cannot yet justify a new capture or affirm existing-evidence readiness. The metadata and authored clear/blocked labels do not establish measured visibility or comparison isolation.

`sight_measurement.py` is an independent saved-source CPU verifier. It requires SHA-bound original frame map, ego motion, sight rays and road geometry; at least 900 consecutive 20 Hz frames; a measured ~180-degree reversal on an original curve/crest highway source; exact-frame nine-body-point rays from both approach directions at 10, 50, 100, 150 and 152.4 m during the turn; and a terrain hit for wholly blocked rays. It rejects missing directions, the 500-foot endpoint, rebinding and stale source hashes. Its 1.4 m virtual lane observer is an engineering convention, not driver-eye perception or a legal visibility verdict. `measurement-contract.json` records this boundary. Six focused CPU tests pass (`cpu-sight-tests.log` SHA-256 `7f0d2263ac4476ffcd41142c6484aeed87df9c33f7ade3e4f46a574e4701e846`). Assignment `--complete` static check passes. Exact strict `--complete --require-delivery-ready` exits 1 on truthful partial (`cpu-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: obtain and re-audit the ten original accepted traces/videos if available in the local operator workspace; implement Native sight-ray acquisition and comparison isolation proof against original sources; only then decide source-backed reuse versus any genuinely missing exact-case construction. The current export cannot establish physical visibility or accepted evidence sufficiency. This is not marked an external blocker; remaining source adapters and audit code are worker-owned.
## 2026-11-23 independent accepted-reuse comparison audit checkpoint

`comparison_audit.py` now reopens and remeasures both hashed original attempts for each of the seven exact pairs in `case-plan.json.accepted_comparisons_pending_original_review`. It binds exact case and recording IDs, the unchanged road-geometry source and curve/crest location, the 900-frame/20 Hz two-direction 500-foot sight contract, and a measured difference in original ray patterns. For the six clear-versus-blocked directional pairs it requires the declared direction to change from zero blocked rays to at least one. The discontinuous-reversal pair requires a distinct measured station pattern; the verifier does not infer continuity or legal driver visibility from its authored label. No accepted recording is newly certified by diagnostic fixtures.

`tests/test_comparison_audit.py` exercises all seven pairs and rejects a wrong recording ID, changed fixed geometry, and a missing measured sight difference. The full focused suite has nine passing tests. Pinned preflight and scoped static pass; strict remains truthful partial because original accepted traces/videos and review proofs are still absent from this export.

Proof hashes: `cpu-sight-tests.log` `c9f528388b73e6992db66ded63f07b607c623b0d14c6b706d11499159eaa77ec`; `cpu-preflight-comparison.log` `eaa2eca1cc9d2e0fad482e7d14cab630f9d2f97fa0ad7caa1a29dde8ca3ae320`; `cpu-static-check.log` `f6d113fe22b0f4b45e4f8e2989aa63145e797a6933508394eb61f31cfa131fbb`; `cpu-strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1).

Next CPU work: bind and re-review original accepted traces/videos for all ten source candidates; compare actual scene, participant, camera and turn conditions; retain zero new captures only if original reuse suffices. Implement any needed Native capture/runner and canonical saved delivery proofs after that review. Physical line of sight and legal perception remain unresolved.
