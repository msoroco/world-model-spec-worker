# testing__C179789__NRS-484B-627-1c__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.627(1)(c) — If any driver or operator of a motor vehicle drives or operates a motor vehicle at a speed so slow as to impede the forward movement of traffic proceeding immediately behind the driver or operator, the driver or operator shall: If the highway is a controlled-access highway, use alternate routes whenever possible.
Assigned branch(es): Controlled-access alternate-route duty with paved-road context..
Cell: C179789 (paved_road, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C179789__NRS-484B-627-1c__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `alternate_route.py` for four exact physical probes: alternate selected, available but not selected, restricted alternate, and ordinary-road classification contrast. The source-gated lazy constructor requests common approach, divergent main/alternate routes, ego and following vehicle and cleans owned actors on failure. Original measurement joins 900 frames, identities, shared segment, following gap, both speeds and actual terminal route. Legal controlled-access classification, so-slow impediment, immediately-behind and possibility judgments remain unresolved.

Four focused CPU tests pass, including all probes and negative route/restriction/source, participant identity, actual-route and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because package status remains partial. The diagnostic graph is synthetic. Physical controlled-access classification and alternate feasibility need original evidence; canonical capture/offline/compatibility, semantic proposals and independent saved delivery/comparison audits remain worker-owned CPU work.

Proof SHA256:

- `alternate_route.py`: `6b5b73b31c758cdd413777ac42a6740cb36cdc83afaf924545409e1e0c618e74`
- `tests/test_alternate_route.py`: `55e235b442438ffddc580b8104bcc9cb3c0c1538c536e4560f9d1e322b692226`
- `cpu-tests.log`: `323bd6fe09a3bf8c87eee4ec31726a753c74f2ce797f59a012790373cfdb8d04`
- `cpu-preflight.log`: `41ce1b504e3260e67e0ddfea9f85c45bdcf874d084c3f9dccb3f7538493ba647`
- `cpu-static-check.log`: `38626eef611456a5d0f0712d46a9ac84a36a01009a280abf0bd6058403581313`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
