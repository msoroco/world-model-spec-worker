# NRS-484B-210-3 at C146314

## Current CPU construction checkpoint

`native/measure_right_pass.py` now reads hashed pavement/shoulder geometry and 600 contiguous 20 Hz vehicle rows, then measures passing overlap, right-side position, full vehicle footprint off the paved portion, and their concurrence. `prove-right-pass.py` retains paved and unpaved-shoulder synthetic traces. Both have 181 right-pass overlap frames (1310–1490). The paved trace has zero off-paved frames; the shoulder trace has 201 off-paved frames, 181 concurrent with the right pass. Two positives and six negatives (changed source hash, absent lead, frame/time gap for each) pass. Proof SHA-256 `0fc4fa21fccaad40fc710f6898bb22559fb4c58f5a808ea5c92961ce11ff1c84`.

`audit-right-pass.py` independently checks the frozen law, retained hashes and raw rows, pavement geometry, fixed longitudinal pass timing and concurrent footprint counts. It passed; audit SHA-256 `5039670842ced3bc379b90f51d51e56387466f764aa2d3b99d230d31f336ac9c`. These are synthetic CPU diagnostics, not physical Native passing, selected delivery, accepted recording, or legal verdict. The law's requirement that the movement *requires* leaving pavement is unresolved by a footprint excursion alone; alternatives and actual paved-surface geometry need exact construction and review. The accepted recording ID remains membership-only without source-hashed equivalence.

Verification commands: `.venv-cpu/bin/python work/training__C146314__NRS-484B-210-3__motor_vehicle_driver/prove-right-pass.py` and `.venv-cpu/bin/python work/training__C146314__NRS-484B-210-3__motor_vehicle_driver/audit-right-pass.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `77949fcaad0c24104d32d7e7fef8aee00308add1f0a66e87b23b602a05b666c8`. `.venv-cpu/bin/python worker_check.py --assignment training__C146314__NRS-484B-210-3__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `fbc373f7883315b6d4ed8e4dc81604c0da155cf825d4b2750fa5ca394eedccc1`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: implement exact Native right-pass routes/controllers and surface geometry, demonstrate whether the off-pavement excursion is necessary for the movement, review accepted-recording source evidence, build each exact 30-second construction with four cameras and risk-justified fallbacks only, run source-bound saved processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_multilane` / `overtake_right` / `other_vehicle`.

Witness branch: Accepted membership requires exact source review.

Comparison variable: `right_pass_paved_surface`. Proposed physical probes: pass on right while retaining full footprint on pavement; pass on right with footprint off pavement. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C146314__NRS-484B-210-3__motor_vehicle_driver/assignment.json`, SHA-256 `3d00cb89cd87a1126cb9a96822f0af2921204bc93e4d20067304f833ed14220c`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: 882987bca0cf436fb50c0cf93c3c8a3b5a3d95d554ae1230ac3a8c1d51904eb0. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no completed compatibility, physical-preparation, semantic, delivery, or comparison audit receipts. Accepted recording IDs are membership context only and lack an equivalence receipt. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and risk-justified fallbacks if a discrete physical failure mode is found; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## Current Native route and saved-measure progress

The frozen `review-context/review.json` describes accepted case `C146314-pavement-entirely-paved` as a Town04 paved right pass, but supplies no source-hashed receipt or frames. It supports the paved comparator description only; equivalence to either new exact case is unproven. `case-plan.json` now binds that review source and the witness file, records the evidence gap and corrects the comparison: lead lateral placement, ego route and resulting paved clearance deliberately differ, while road, actor, law, speed requests, timing and cameras are held fixed.

`native/geometry.py` defines a 350 m one-way two-paved-lane road and a shoulder lane. `native/runner.py` authors separate ego/lead routes, four source cameras, 600 frames, original body corners, trace, frame joins and Native restoration/seal. Its CPU `--check` passes; no CARLA execution is claimed. `native/necessity.py` computes the geometric right-side corridor for a 1.8 m subject body with 0.4 m clearance: 5.1 m available for the paved comparator versus 1.1 m for the shoulder case, against 2.2 m needed. `native/prove_routes.py` binds its code hashes and passes. This is an engineering geometry plan; actual vehicle dimensions, motion, map readback and shoulder material require original review.

`native/measure_original.py` independently measures full-body behind/overlap/ahead timing, right-side position, concurrent off-paved footprint and paved-clearance feasibility from source-shaped body rows with exact frame, time and road-hash joins. `native/prove_measure_original.py` passes two 600-frame positives and six missing/changed-source negatives. Its proof is diagnostic, with no legal verdict. `prove-right-pass.py` now creates temporary negative-test directories under `.runtime-work/`; its retained proof hash is unchanged.

The remaining CPU sequence is per-case construction and config materialization, case-specific finalizer and source-hashed fixture recipes, offline/public compatibility and saved Core/Lean/final decode tests, semantic stage proposals, and independent delivery/comparison audits. Exact `worker_check.py --assignment training__C146314__NRS-484B-210-3__motor_vehicle_driver --complete` passes as a partial checkpoint. Strict readiness has not passed.

## Exact construction and CPU fixture checkpoint

Two selected case constructions are now source-bound in `native/probe_a-construction.json` and `native/probe_b-construction.json`. The same one-way road, vehicles, longitudinal speed requests, timing and four cameras are fixed. Lead lateral placement and ego right-pass route differ by design. `runtime.py offline` passes for both exact cases, including materialized runner `--check` and unit tests. The two 600-frame source-hashed CPU diagnostic fixture recipes materialize, with four decoded camera videos each. `native/finalize.py` succeeds on both fixtures and its saved-only proof passes two positives plus four missing/changed-source negatives (SHA-256 `9370341f904622574fb04a8995f996ccf0765e108d77ef0b6fcc944e098d6ed3`). These fixtures verify software joins only; they are not original Native acquisition, physical pavement/material proof, or accepted delivery.

`proposals/cases.json`, per-case measurement contracts and a draft execution manifest now bind the two explicit case identities for public compatibility. Public compatibility, physical-preparation, semantic and independent delivery/comparison audits are next. Status remains partial, and the exact scoped `--complete` check passes at this checkpoint.
