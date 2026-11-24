# testing__C204980__NRS-484B-213-2b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.213(2)(b); with 484B.213(3) — A vehicle must not be driven to the left side of the highway at any time: When approaching within 100 feet or traversing any intersection or railroad grade crossing. Subsection 2 does not apply upon a one-way highway.
Assigned branch(es): railroad grade-crossing approach and traversal.
Cell: C204980 (rail_crossing, travel, centerline); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C204980__NRS-484B-213-2b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `rail_left.py` with six physical probes: left at 101, 100 and 99 feet from the constructed near crossing edge; right at 99 feet; left while traversing; and one-way-highway exception context. The source-gated lazy constructor requires highway, rail carrier, non-streetcar, at-grade crossing, centerline and body-reference sources. Original measurement joins 900 frames and computes leading-body distance in feet, crossing overlap and body lateral extent. The 100-foot statute is preserved; near-edge/leading-body choices are explicitly engineering assumptions, not legal definitions.

Four focused CPU tests pass, including all six cases and negative rail/streetcar, one-way, source, identity, distance and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because package status remains partial. The diagnostic distance targets are synthetic. Physical qualification and placement, canonical capture/offline/compatibility, semantic proposals and independent saved delivery/comparison audits remain worker-owned CPU work.

Proof SHA256:

- `rail_left.py`: `cb0de54ccd6cb754bb065aa35bb10a120dda67022d24a5947fbbb7aefeb1737e`
- `tests/test_rail_left.py`: `8dca5b29bacb76974134b0b751d68362e45644ac00892ba795ccd2dc6a6c8282`
- `cpu-tests.log`: `3b44372fab70e2fbf5fabe45a2e0ca5e1711ec12e86da949211a4c644c7ab171`
- `cpu-preflight.log`: `4dc3b3e0ca19ce4ee9610f271105b424992e04c016a864b076d846c5231a5fa7`
- `cpu-static-check.log`: `c21bd9102992827343d826e9169bf9caadc9c3f5b34d1f0d9451ddcff1be8f30`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
