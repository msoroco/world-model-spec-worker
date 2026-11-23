# testing__C102642__NRS-484B-153-2__motor_vehicle_driver

Status: partial CPU construction draft. Five exact cases and three controlled comparisons are proposed; no recording has been executed or accepted.

Exact law: NRS 484B.153(2) — A person shall not open the door of or board or alight from the side of a vehicle which is closest to passing traffic in such a manner as to interfere with moving vehicular traffic.
Assigned branch(es): Door opening during loading in a hill-crest scene.
Cell: C102642 (hill_crest, load_unload, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C102642__NRS-484B-153-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The frozen accepted recording inventory is empty. The exact law has three act alternatives: open a door, board, and alight. All require the actor and side closest to passing traffic and the moving-traffic interference context; no numerical legal interference threshold is supplied. The revised `case-plan.json` names five exact cases: `open_near_overlap`, `open_near_clear`, `open_far_side`, `board_near`, and `alight_near`, each prefixed by this assignment ID. It declares controlled `door_sweep_clearance`, `door_side`, and `selected_act` comparisons. These are planned recordings, not executed or accepted evidence.

`door_interaction.py` now provides an actual CARLA front-door command hook, geometric passing-side classification, synchronized original-frame checks, a conservative door-sweep proximity proxy, and a route-grade reversal and loading-site spatial check. It rejects centerline-crossing traffic, incomplete source joins and a route without a unique crest. The proxy explicitly leaves legal interference unresolved and requires original Native door/body vertices before any acceptance claim. Boarding and alighting still require executable capture; a door command is not their proof.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C102642__NRS-484B-153-2__motor_vehicle_driver/tests -v` passed 4 tests; log `cpu-door-geometry-tests.log`, SHA256 `0fb180b74d89c13e77dc9e12c783f6193cda9685b2d95cd69f3e2eed50e46a3c`. `.venv-cpu/bin/python runtime.py preflight` passed with Lean 4.28.0 and pinned CPU packages. `.venv-cpu/bin/python worker_check.py --updates` reported version 0 and no paused assignments. The exact `worker_check.py --assignment testing__C102642__NRS-484B-153-2__motor_vehicle_driver --complete --require-delivery-ready` still fails with `Preparation acceptance failed: partial/missing packages remain`, consistent with `result.json` status `partial`.

Next CPU work: bind an exact surveyed hill-crest loading site and parked/passing vehicle poses into a lazy Native runner; capture original door articulation and driver act, moving body and response, and four-camera frame identities; write source-bound finalization for each act; complete canonical semantic proposals, per-case constructions, manifest, pinned offline/positive-negative/saved-only proofs, and independent delivery/comparison auditors. Run the exact strict assignment gate after all CPU proofs pass. Later physical motion, visibility and capture-quality review remain GPU checks.

## 2026-11-24 saved-source measurement checkpoint

`delivery_measure.py` adds an executable saved-only CLI accepting an original Native trace path, SHA256, exact case, act and side. It rejects stale source bytes, wrong case/source kind, missing driver or observed act, noncontiguous 20 Hz frame/time identities, incomplete four-camera frame joins, absent original act/passing-body vertices or traffic response, ambiguous traffic side and no moving overlap. It reports original-frame body gaps and response history while leaving legal interference unresolved. `audit_source_pair` independently remeasures two sealed traces and rejects changed fixed scene context or absent declared difference. The added tests use small synthetic traces strictly as software checks, not physical evidence.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C102642__NRS-484B-153-2__motor_vehicle_driver/tests -v` passed 11 tests; `cpu-tests.log` SHA256 `73bde33d1fd3006cb05a7e91d94015699e3ba99f2c0e244c98740d2ed9e05de6`. The pinned `.venv-cpu/bin/python runtime.py preflight` passed with Lean 4.28.0.

Next CPU work: implement the Native runner and surveyed hill-crest loading site, original door/body and driver boarding/alighting capture, exact five-case construction bundles and manifest, semantic proposals, pinned offline and positive/negative compatibility and saved-only proofs, and the full independent delivery audit. The measurement CLI is only one component of the required saved processor. Keep partial until the exact strict gate passes.

## 2026-11-24 hill-crest site preflight checkpoint

`site_contract.py` now validates a source-hashed original map-survey packet for the five exact actions, a measured route grade reversal, loading-site distance from surveyed road edge, explicit loading-zone governance source, passing route side, actor/vehicle identities and case-specific act/side/clearance choice. A synthetic packet tests the verifier for both approach sides and missing grade/governance; it does not establish that a real site exists. The actual original survey packet and lazy Native construction/capture are still CPU work.

All 14 focused tests pass in `cpu-tests.log` (SHA256 `47d155784e36f22bfe9bb67672275ce945ace732c4ce59eef8119a301d96228c`).

Assignment gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C102642__NRS-484B-153-2__motor_vehicle_driver --complete` exit 0 (`static_checks_passed: true`). The exact command with `--require-delivery-ready` exits 1 at `Preparation acceptance failed: partial/missing packages remain`, matching the truthful partial result. The remaining items are implementation tasks, not an external blocker.
