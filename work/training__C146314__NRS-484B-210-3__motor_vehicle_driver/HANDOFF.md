# NRS-484B-210-3 at C146314

## Current CPU construction checkpoint

`native/measure_right_pass.py` now reads hashed pavement/shoulder geometry and 600 contiguous 20 Hz vehicle rows, then measures passing overlap, right-side position, full vehicle footprint off the paved portion, and their concurrence. `prove-right-pass.py` retains paved and unpaved-shoulder synthetic traces. Both have 181 right-pass overlap frames (1310–1490). The paved trace has zero off-paved frames; the shoulder trace has 201 off-paved frames, 181 concurrent with the right pass. Two positives and six negatives (changed source hash, absent lead, frame/time gap for each) pass. Proof SHA-256 `0fc4fa21fccaad40fc710f6898bb22559fb4c58f5a808ea5c92961ce11ff1c84`.

`audit-right-pass.py` independently checks the frozen law, retained hashes and raw rows, pavement geometry, fixed longitudinal pass timing and concurrent footprint counts. It passed; audit SHA-256 `5039670842ced3bc379b90f51d51e56387466f764aa2d3b99d230d31f336ac9c`. These are synthetic CPU diagnostics, not physical Native passing, selected delivery, accepted recording, or legal verdict. The law's requirement that the movement *requires* leaving pavement is unresolved by a footprint excursion alone; alternatives and actual paved-surface geometry need exact construction and review. The accepted recording ID remains membership-only without source-hashed equivalence.

Verification commands: `.venv-cpu/bin/python work/training__C146314__NRS-484B-210-3__motor_vehicle_driver/prove-right-pass.py` and `.venv-cpu/bin/python work/training__C146314__NRS-484B-210-3__motor_vehicle_driver/audit-right-pass.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `77949fcaad0c24104d32d7e7fef8aee00308add1f0a66e87b23b602a05b666c8`. `.venv-cpu/bin/python worker_check.py --assignment training__C146314__NRS-484B-210-3__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `fbc373f7883315b6d4ed8e4dc81604c0da155cf825d4b2750fa5ca394eedccc1`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: implement exact Native right-pass routes/controllers and surface geometry, demonstrate whether the off-pavement excursion is necessary for the movement, review accepted-recording source evidence, build four distinct 30-second constructions per selected case with four cameras, run source-bound saved processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_multilane` / `overtake_right` / `other_vehicle`.

Witness branch: Accepted membership requires exact source review.

Comparison variable: `right_pass_paved_surface`. Proposed physical probes: pass on right while retaining full footprint on pavement; pass on right with footprint off pavement. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C146314__NRS-484B-210-3__motor_vehicle_driver/assignment.json`, SHA-256 `ea2c3271bcd5fe97804339bcfcfdce0f62ed54a615f51a76f4242d85eae94a97`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: 882987bca0cf436fb50c0cf93c3c8a3b5a3d95d554ae1230ac3a8c1d51904eb0. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Accepted recording IDs are membership context only and lack an equivalence receipt. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
