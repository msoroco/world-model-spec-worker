# testing__C125714__NRS-484B-203-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.203(1) — Drivers of vehicles proceeding in opposite directions shall pass each other keeping to the right, and upon highways having width for not more than one line of traffic in each direction, each driver shall give to the other at least one-half of the paved portion of the highway as nearly as possible.
Assigned branch(es): Opposing pass on an undivided approach in a median-opening scene.
Cell: C125714 (median_opening, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-203-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

Exact cases in `case-plan.json`: `__right_half`, `__wrong_side`, `__left_encroachment`, `__right_constrained`. Comparisons: `direction_relative_right_side`, `half_paved_allocation`, `physical_constraint_context`. The `exact-text` topic is mapped to all three. There are no frozen accepted recordings or law-specific judgment-range entries; this is a planned capture package, not a reuse. The conditional traffic-line capacity comes from a source-confirmed map packet, not an invented width cutoff. The phrase “as nearly as possible” remains an unresolved human legal judgment.

`opposing_pass.py` implements SHA-sealed source loading, an undivided median-approach and opposing-lane route gate, variant-specific lateral route requests, a CARLA-lazy two-actor spawn/readback with rollback, continuous 20 Hz original-history pass measurements, a write-once saved finalizer, and a comparison audit that rejects missing source or altered fixed conditions. `tests/test_opposing_pass.py` exercises the positive and rejection branches. The site packet must be obtained from original Native map review before any actor construction; the CPU fake establishes software behavior only. Physical pass clearance, camera visibility, and actual motion remain GPU checks.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C125714__NRS-484B-203-1__motor_vehicle_driver/tests -v` passed 10 tests (`cpu-tests.log`, SHA256 34a12f33c74a64af2673fc61d2f3ba5141a0916c024ed532aec66bc412b6e7ac). `.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-203-1__motor_vehicle_driver --complete` passed static checks (`cpu-static-check.log`). Exact strict gate failed `Preparation acceptance failed: partial/missing packages remain` (`cpu-strict-check.log`); no ready claim.

Next CPU work: bind a source-reviewed map packet and four case-specific Native controller/capture bundles; create canonical stage proposals and manifest with physical-risk candidates, source-hashed diagnostic fixtures and exact offline/positive-negative compatibility receipts; run saved-only processing plus independent delivery/comparison audits; rerun exact strict gate.

A source-defined Native road frame now projects both station/lateral routes to world XYZ in `world_routes`; missing or nonunit axes fail closed. The focused suite passes 11 tests, `cpu-tests.log` SHA256 a1045318970b914889ca2375e5add05fbf24d192a3ff243ecaf051deddb04007. This supersedes the earlier 10-test hash.

## 2026-11-23 original opposing-body acquisition checkpoint

`native_history.py` now accepts a supplied Native tick adapter and a SHA-bound reviewed map packet. For each original 20 Hz tick it retains the CARLA frame/time, actor IDs and eight world-space body vertices, projects both bodies and actual velocities into the source-defined road frame, samples the surveyed paved boundaries, and seals a once-only trace. The output feeds `opposing_pass.measure` and `finalize_sealed`; route requests cannot substitute for observed bodies. Production requires 900 frames; short CPU fixtures must explicitly mark themselves diagnostic. The adapter still owns the world lease, actor control, cameras and cleanup.

The focused suite passed 14 tests. A three-frame diagnostic source executed projection, passing-interval measurement and saved finalization; frame gap, missing vertex, unsealed map, false attestation and short production capture rejected. Pinned preflight and scoped static `--complete` passed; exact scoped strict exited 1 on truthful partial status. Commands and log hashes are recorded in `result.json`. No execution manifest exists yet, so pinned offline cannot run for an exact bundle at this checkpoint.

Next CPU work: bind a source-reviewed median-opening site to actual Native waypoints and controller/world lifecycle, add synchronized four-camera original capture, author four inline constructions with exact manifest, semantic stages, diagnostic recipes, positive and missing-source compatibility, saved-only delivery and independent audits. Physical passing clearance, pixels and legal “as nearly as possible” judgment remain unverified.

## 2026-11-24 synchronized Native camera checkpoint

`native_history.capture` can now retain four PNG camera views on the same original 20 Hz ticks as the opposing actor body trace. It seals a per-frame camera manifest with original Native frame/time and SHA256 for every image. `audit_media` independently reopens and decodes each image, verifies hashes, and joins all four views to actor frame/time. Three-frame synthetic fixtures prove positive join and rejection of camera omission, changed image bytes and a resealed clock mismatch. The production path still requires 900 frames; the fixture is explicitly diagnostic and claims no physical or legal acceptance.

The focused suite passed 16 tests; pinned preflight and scoped static passed; exact scoped strict exited 1 on truthful partial. Commands and log hashes are in `result.json`. Remaining CPU construction: source-reviewed median-opening map, actual CARLA adapter/world control, four canonical inline bundles and manifest, semantic proposals, pinned offline/compatibility, complete saved delivery and independent comparison audit.

## 2026-11-24 original CARLA opposing-body adapter checkpoint

`carla_adapter.py:CarlaOpposingAdapter` now binds the SHA256 of a reviewed packet and exact live map name, requires a 20 Hz synchronous Native world and distinct actors, reads eight body vertices and measured velocity for both actors, and joins four original camera image frames to the same world tick. The adapter emits source packets consumed by the existing 900-frame `native_history.capture`; a short diagnostic test proves the join and rejects changed map bytes/name, camera drift and actor alias. It does not spawn/control vehicles or attest that the source packet itself was physically reviewed.

The 18-test assignment suite, pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Four SHA-bound logs are in `result.json`. Next CPU work: source-reviewed original median-opening map and world/actor/controller lifecycle, four canonical bundles and semantic proposals, exact offline/compatibility/process-saved receipts and independent delivery audit. Physical passing clearance and pixels remain unverified.
