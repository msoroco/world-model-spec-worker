# NRS-484B-260 at C177626

## Current CPU construction checkpoint

`native/measure_private_entry.py` now reads hashed private-way/highway geometry and 600 contiguous 20 Hz actor rows, validates two approaching highway vehicles, and measures conflict-point arrival order. `prove-private-entry.py` retains two synthetic 30-second traces with identical highway vehicles arriving at frames 1120 and 1200. The yielding probe puts ego at the conflict point at frame 1240 (both before ego); the early-entry probe puts ego there at frame 1160 (only one before ego). Two positives and six negatives (changed source hash, absent approaching vehicle, frame/time gap for each probe) pass. Proof SHA-256 `af5adbee0ea338e7fbe19b7c10963b99d52183d3da1618689b7219d106cda832`.

`audit-private-entry.py` independently checks the frozen law's *all vehicles approaching* scope, retained hashes, raw actor rows, geometry, fixed highway trajectories and arrival order. It passed; audit SHA-256 `3a474453552e1d07921f11bd08659c73c282293f1c210ca7bd3107e0f3f2918b`. These are synthetic CPU diagnostics, not Native crossing, selected delivery, accepted evidence, or a right-of-way verdict. Conflict arrival order alone does not settle yielding, and actual capture must inventory every approaching highway vehicle.

Verification commands: `.venv-cpu/bin/python work/training__C177626__NRS-484B-260__motor_vehicle_driver/prove-private-entry.py` and `.venv-cpu/bin/python work/training__C177626__NRS-484B-260__motor_vehicle_driver/audit-private-entry.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `de5382115e9645897989374696717da518f6d0f3c2117e0dc37e773b137a0362`. `.venv-cpu/bin/python worker_check.py --assignment training__C177626__NRS-484B-260__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `213dd94956d48b2ac509d024d2085b53bf295d0d337f0833789d6b04e5070b1b`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: construct exact Native private-way/highway geometry and controllers, inventory all approaching vehicles and continuous conflict occupancy, build four distinct 30-second constructions per selected case with four cameras, run saved-source processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `paved_road` / `enter_road` / `other_vehicle`.

Witness branch: enter_paved_highway_from_private_way.

Comparison variable: `private_way_entry_yield`. Proposed physical probes: yield to approaching highway vehicle; enter ahead of approaching highway vehicle. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C177626__NRS-484B-260__motor_vehicle_driver/assignment.json`, SHA-256 `2cffece8494bb616f7f3d2d713f2c9fd9573f512f246d3b29c88732522982904`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
