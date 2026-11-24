# testing__C227824__NRS-484B-307-9c__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(9)(c) — Where the signal is a steady red with a green turn arrow: Pedestrians facing such a signal shall not enter the highway, unless permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): Pedestrian crossing entry.
Cell: C227824 (road, cross_road, traffic_light); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C227824__NRS-484B-307-9c__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `ped_entry.py` for four exact probes: entry/wait under official steady red concurrent green turn arrow, with no other device or a separately displayed WALK device. The source-gated lazy constructor requests signal states and pedestrian route and cleans owned actor on failure. Original measurement joins 900 frames, afoot/facing/signal condition and physical body entry from outside the highway boundary. Vehicle green arrow is never converted to pedestrian permission; NRS 484B.283 exception conditions remain unresolved.

Four focused CPU tests pass, including all probes and negative source, signal, identity, missing entry and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because package status remains partial. Diagnostic signal/boundary values are synthetic; physical signal timing/facing and highway dedication/public use require original review. Canonical capture/offline/compatibility, semantic proposals and independent saved delivery/comparison audits remain worker-owned CPU work.

Proof SHA256:

- `ped_entry.py`: `9d72881272a119de16f545580ba80277ac28e982dbeb705ea41aea67bab0fa96`
- `tests/test_ped_entry.py`: `023d917ed4d33a7eb38763ffb9c59e94cd4af62108361f0c45e31d3b290cda53`
- `cpu-tests.log`: `bc2a213d060c2e80e78b44e363dcbbd71eee3743856a567f25772a36c26b607b`
- `cpu-preflight.log`: `69ff3574bc5a7d8045154eb226b28419db30e3f0f18e0e8889ee126635ebf914`
- `cpu-static-check.log`: `0b131134897389f4624eb3c43618609da130b565fe185124a9cbcb33f4a5fb22`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
