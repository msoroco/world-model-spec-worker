# NRS-484B-560-3 at C202463

## Current CPU construction checkpoint

`native/measure_rail_queue.py` now reads hashed rail-crossing/highway geometry, 600 joined 20 Hz gate rows and two-vehicle rows, and measures right-edge gap and side-by-side queue frames during a gate stop indication. `prove-rail-queue.py` retains three synthetic 30-second diagnostics: right single queue (0.6 m measured right-edge gap, no abreast frames), left single queue (3.6 m gap, no abreast frames), and left abreast queue (3.6 m gap, 300 abreast frames). Each has 300 stopped frames during the authored gate-stop interval. Three positives and nine negatives (changed source hash, absent other vehicle, gate/actor frame gap for each) pass. Proof SHA-256 `7026c1d9a9c4f20c30dfbafbeccd45ec9a2c759ba6b19eb7765f3202613038de`.

`audit-rail-queue.py` independently checks the frozen law, retained hashes, raw gate/actor joins, actual authored two-lane count, right-edge gaps, and longitudinal/lateral queue arrangement. It passed; audit SHA-256 `ead9804c88bf9c136142ab0ce547b12414e6f037ca945a9a5dbc726e244bfd22`. The four-or-more-marked-lanes qualification applies only to the two-lanes prohibition; the separate far-right duty remains. These synthetic diagnostics do not establish an independently supported required stop, rightmost possible position, Native motion, selected delivery, accepted evidence, or legal verdict. The conditional frozen witness requires gate instruction authority, gate geometry/motion/barrier coverage, supported crossing path, road boundaries, constraints and surrounding traffic to be separately sourced.

Verification commands: `.venv-cpu/bin/python work/training__C202463__NRS-484B-560-3__motor_vehicle_driver/prove-rail-queue.py` and `.venv-cpu/bin/python work/training__C202463__NRS-484B-560-3__motor_vehicle_driver/audit-rail-queue.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `61c57709831ac2c2ab34533f450cf66a4e39c9486d60993c864459cdd74f612c`. `.venv-cpu/bin/python worker_check.py --assignment training__C202463__NRS-484B-560-3__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `8d9e6883744c6116adea98179c15250e86ce73de69f97cdbde0564308d985ff6`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: construct exact Native gate-controlled crossing and highway boundaries, prove a required-stop basis separately from gate closure/train approach, establish full marked-lane count and available right-side space, build four distinct 30-second constructions per selected case with four cameras, run saved-source processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `rail_crossing` / `cross_railway` / `rail_gate`.

Witness branch: Both duties during a gate-related required stopping episode..

Comparison variable: `rail_stop_lateral_position_and_queue`. Proposed physical probes: stop rightward in one queue; stop leftward or form second queue without four marked lanes. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C202463__NRS-484B-560-3__motor_vehicle_driver/assignment.json`, SHA-256 `eb89e7603bbc437b9d04a88accaaa576c2eb68d62288d65746fa4a0b39f8253d`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
