# NRS-484B-227-1 at C124163

## Current CPU construction checkpoint

`native/measure_median.py` implements source-hashed polygon overlap measurements for median, physical opening, and continuous divider. `prove-median-crossing.py` retains two 600-frame, 20 Hz textual source fixtures and proves the measurement output and six rejection paths (changed source hash, synthetic-to-Native relabel, and frame/time gap for each probe). The source traces differ only by a 12 m x translation with fixed timing, y path, speed, and body shape: probe A has 85 opening-overlap frames and zero barrier-overlap frames; probe B has zero opening-overlap frames and 85 barrier-overlap frames. Proof SHA-256: `6f118d964efe24652692bc657a94a77e600991eb2c00259a063fa9529e8fcc68`.

`audit-median-crossing.py` independently reads the frozen law, retained geometry and raw body rows, checks source hashes and provenance, recomputes overlap counts, and verifies the controlled difference. Audit SHA-256: `2c9d406f744e36352e4fa37cc1143ea943eaad859e26874aac9457e84d32eb9b`; passed. These fixtures are synthetic geometry diagnostics only. They are not a left-turn Native route, public-authority establishment, selected delivery case, accepted recording, or legal verdict.

Verification commands: `.venv-cpu/bin/python work/training__C124163__NRS-484B-227-1__motor_vehicle_driver/prove-median-crossing.py` and `.venv-cpu/bin/python work/training__C124163__NRS-484B-227-1__motor_vehicle_driver/audit-median-crossing.py` both exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `cd831dd8d5ae1839c2ef54d382d288b90284a3b4df30538bc68f298cdc72db80`. `.venv-cpu/bin/python worker_check.py --assignment training__C124163__NRS-484B-227-1__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `df6f0553cf6759321f29b4479cedb806317e215adb6fe3cfe3429bb7e4822436`. The scoped complete check establishes a valid partial checkpoint, not delivery readiness.

Remaining worker-owned CPU work: implement exact left-turn Native routes and controllers through an established opening and across a continuous divider in the frozen cell; preserve the statutory right-hand-roadway and crossover/intersection alternatives; build four distinct 30-second constructions per selected case with four camera sources, saved-source measurement/finalization, current offline and compatibility proofs including missing-source negatives, Core/Lean/final decode, independent delivery and comparison audits, and accepted-recording equivalence review. Keep status partial until assignment-scoped strict readiness passes.

Actor: `motor_vehicle_driver`. Frozen cell: `median_opening` / `left_turn` / `median_barrier`.

Witness branch: Left turn through a physical median opening; exception scope remains unresolved..

Comparison variable: `physical_median_crossing_location`. Proposed physical probes: turn through physical authorized opening; turn across continuous dividing barrier. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C124163__NRS-484B-227-1__motor_vehicle_driver/assignment.json`, SHA-256 `a365707525f262403e8c48f2df64a17c7fbb036483482a0c2fda157525163fe1`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: 0819c0dc3305d9f0ce7010fdc279a2375e24bde9fb722fa8e3370f2353181314, 7ba1ab4a7268ef149ff00d8fd63eb0d32ba63cc6801f9613084f82cc052ada54, c36e1b5028570eb2390af59a44abe48491963c8ab9a1ea17966e997c17c774da, e251930ca4dd928e72c50e8033d25dcedf03956932c82816fe75ea2c8c46b240. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Accepted recording IDs are membership context only and lack an equivalence receipt. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
