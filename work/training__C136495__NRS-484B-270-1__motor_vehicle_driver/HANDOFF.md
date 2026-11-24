# NRS-484B-270-1 at C136495

## Current CPU construction checkpoint

`native/measure_rider_response.py` now reads source-hashed bicycle/vehicle geometry and 600 contiguous 20 Hz actor rows to measure lateral surface gap, near frames, first vehicle lateral movement, and first rider speed reduction. `prove-rider-response.py` retains clear and lateral-intrusion synthetic traces. The clear trace has zero near frames; the intrusion trace has 400 near frames, with vehicle lateral movement starting at frame 1200 and scripted rider speed reduction at frame 1220. Two positives and six negatives (changed source hash, absent rider, frame/time gap for each trace) pass. Proof SHA-256 `8b8a227b70546ba713aa2015198fc53f1562c3d783782f1b27e29d3c48f2a6d9`.

`audit-rider-response.py` independently checks frozen statutory terms, retained source hashes, geometry, raw frame/time rows, gap counts and event order. It passed; audit SHA-256 `b278260031521e40512940251d46ac200b72152464ade868db5b432f8eddd400`. These are synthetic CPU diagnostics, not Native rider motion, causation, a lawful-riding determination, driver intent evidence, selected delivery, accepted recording, or legal verdict. The scripted response cannot establish interference.

Verification commands: `.venv-cpu/bin/python work/training__C136495__NRS-484B-270-1__motor_vehicle_driver/prove-rider-response.py` and `.venv-cpu/bin/python work/training__C136495__NRS-484B-270-1__motor_vehicle_driver/audit-rider-response.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `6e0907202316d34abcbb0023b15a4583d834c3c6e7b1ca60d5694e4f4d4a24a3`. `.venv-cpu/bin/python worker_check.py --assignment training__C136495__NRS-484B-270-1__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `b52db504e9838c9fe02ee55d05871f04add3ae44b665f7650532b0ed397ad534`. This check validates a partial checkpoint only.

Remaining worker-owned CPU work: build exact Native narrow-road vehicle/cyclist routes and controllers, source-ground rider movement and lawful status, a controlled interference comparison and separate intent evidence plan, cover electric bicycle/electric scooter alternatives, four distinct 30-second constructions per selected case, four-camera capture, saved-source processing and Core/Lean/final decode positives/negatives, and independent delivery/comparison audits. Keep partial until the scoped strict gate passes.

Actor: `motor_vehicle_driver`. Frozen cell: `narrow_road` / `travel` / `cyclist`.

Witness branch: Bicycle rider.

Comparison variable: `rider_interference_and_intent`. Proposed physical probes: travel without interfering with lawful rider; interfere with lawful rider; intent requires separate evidence. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C136495__NRS-484B-270-1__motor_vehicle_driver/assignment.json`, SHA-256 `b4c89dfdc8b6525398cdc5d04f14dece2c71f359aeca8f3309db4ff9e5f82d9d`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
