# training__C229398__NRS-484B-450-1i__motor_vehicle_driver

Status: partial. This is a source-grounded CPU diagnostic checkpoint, not a deployable delivery package.

Exact law: A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within 50 feet of the nearest rail of a railroad.

Selected witness scope: Curbside parking near a railroad rail.. The case plan inventories 3 source topics and drafts one controlled comparison on `vehicle_distance_to_nearest_rail`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining CPU work: acquire real Native rail/vehicle sources in a selected construction, run exact offline/compatibility/saved proofs, implement exception probes and independent acceptance/comparison audits. The 600-frame source-only meter below does not prove physical realization.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Measure vehicle stopping/standing/parking footprint to the nearest physical railroad rail across the 50-foot boundary.

Legal limit: The nearest rail, not the crossing center or an abstract sign, defines distance.

## 2026-11-23 rail footprint CPU checkpoint

The exact unselected construction is `native/unselected-rail-construction.json`. It holds 20 Hz, 600 frames and all four source cameras fixed; the two proposed curbside parking conditions differ only in target body footprint gap to surveyed nearest rail (12.5 m versus 16.5 m in the diagnostic). These are engineering placements to test the statutory 50-foot condition, not legal outcomes. Both physical rails must be independently surveyed; a crossing center or sign is not a substitute.

`native/rail_footprint_meter.py` derives the minimum vehicle polygon-edge to rail-polyline distance from raw per-frame footprint and rail geometry. It requires pose, extent, velocity and rail-source references, a continuous 600-frame/20 Hz map, and a source for any non-unknown halt reason. It preserves the traffic-conflict exception reason as data without inferring whether it legally applies. `native/prove_rail_footprint.py` exercises inside/outside/forced-halt 600-frame synthetic packets and six missing-source/cadence negatives. Synthetic fixtures are labelled `synthetic_native_sample`; there is no original Native motion or legal compliance claim.

Proof: `.venv-cpu/bin/python work/training__C229398__NRS-484B-450-1i__motor_vehicle_driver/native/prove_rail_footprint.py` exits 0. Log `native/rail-footprint-proof.log` SHA-256 fd3184cadd330f8fdae0037b18bb8f6fef643324a79e18dfd08dce57441d7a04. Meter SHA-256 6d3f4b98d2a90a97ffa90e36fd3470a059b060b56ec6164819ab3dc06626f545; construction SHA-256 234e364c046deaac19cddb69ed09b6c01319b5245a51cbe20d6c3a94c298728f. Pinned `runtime.py preflight` passes. Next: bind this source design to a real map/Native acquisition and exact selected cases, prove four-camera capture and saved processing for one primary then linked condition/fallbacks, and audit directions/law/officer/device alternatives independently.

The exact unselected condition-A offline bundle is `native/rail-offline-construction.json` (SHA-256 5f0aabc6c29846b35c36220dc063cd2f791e90833d1f1f082b3cd79016833a83), bound by `draft-rail-offline-manifest.json` (SHA-256 66d262dbf04ce87c26831d474a1f63e48b963002082a854270f464e84c988f22). Pinned `runtime.py offline --manifest ... --case ...condition_a --output .runtime-work/c229398-rail-offline-primary-v2-20261123` exits 0 with four unit tests and no simulation. Returned log `native/rail-offline-primary.log` SHA-256 4794dac0c6b373a1be526367bab739d9130ea8e2251f89c421dc6ce73fac3ee9. The first attempt failed because the materialized test imported `rail_runner` instead of `runner`; the import was repaired and a fresh exact bundle passed. This offline proof checks only the draft contract and source camera profile; it is not compatibility, saved processing or physical evidence.

## 2026-11-27 original rail source join adapter

`native/rail_source_contract.py` now defines a prospective sealed input set with both original physical rail polylines, 600 Native actor rows, an exact 20 Hz frame map and four camera file hashes. It derives the four vehicle-footprint corners from sourced pose, yaw and bounding-box extent before invoking the nearest-rail meter. The adapter rejects missing or altered survey, actor, frame-map and camera source bytes. `native/prove_rail_source.py` passed one synthetic 600-frame source-shaped positive and four changed-source negatives; log `native/rail-source-shape-proof.log` SHA-256 `b63ce3bc9f4d17bc0d41fe16e396ef37507fb8482afe7ee512ea1dc753750f29`. These tests do not decode video, acquire a physical rail, establish authority or prove legal applicability. The Native acquisition runner and selected public/saved/semantic/audit chain are still pending.
