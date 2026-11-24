# NRS-484B-587-2a at C179776

## Current CPU construction checkpoint

`native/measure_lane_boundary.py` now reads hashed controlled-access lane/shoulder geometry and 600 contiguous 20 Hz vehicle rows, then measures whether the full vehicle footprint stays within marked lanes or occupies the paved shoulder. `prove-lane-boundary.py` retains marked-lane and shoulder synthetic traces with fixed geometry and longitudinal motion. The marked-lane trace has zero outside-lane frames; the shifted trace has 400 outside-lane and 400 fully paved-shoulder frames, first outside at frame 1200. Two positives and six negatives (changed source hash, absent vehicle identity, frame/time gap for each) pass. Proof SHA-256 `82de2691344a4ff2341d05755942c96d7bff3b4b24d1563e7fd12509a969f48e`.

`audit-lane-boundary.py` independently checks the frozen law and its emergency, subsection 3 and signed special-vehicle exceptions, retained source hashes, raw frames, fixed longitudinal motion, and footprint counts. It passed; audit SHA-256 `b9dbfa0a9d582ec20a523f9e7adda4d79aa423fe65cb88147d605bc29d3ee454`. These are synthetic CPU diagnostics, not Native highway travel, selected delivery, accepted evidence, or legal verdict. Exception applicability remains unresolved; paved shoulder occupancy alone cannot establish a violation.

Verification commands: `.venv-cpu/bin/python work/training__C179776__NRS-484B-587-2a__motor_vehicle_driver/prove-lane-boundary.py` and `.venv-cpu/bin/python work/training__C179776__NRS-484B-587-2a__motor_vehicle_driver/audit-lane-boundary.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `b47c8650d274c92581a536afc25bc07a7ff8a55003e279f8007d9decb2ae7472`. `.venv-cpu/bin/python worker_check.py --assignment training__C179776__NRS-484B-587-2a__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `908abd6d25a34aa88b6a3d0ed122bf1f2576e1fe91e04ae5e258424de60e66be`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: construct exact Native controlled-access lanes and paved shoulder with marked entrance/exit lanes, source emergency duration, subsection 3 authorization, special vehicle class and lawfully placed sign branches, build four distinct 30-second constructions per selected case with four cameras, run saved-source processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `paved_road` / `travel` / `lane_marking`.

Witness branch: Outside-lane travel on a paved highway segment.

Comparison variable: `controlled_access_lane_occupancy`. Proposed physical probes: remain in marked travel lane; drive beyond marked lane without documented exception. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C179776__NRS-484B-587-2a__motor_vehicle_driver/assignment.json`, SHA-256 `bb568d7bde0130c99f3c6aa3a8b5e98e2b07afe12db34087fd6fd7149ace5a98`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
