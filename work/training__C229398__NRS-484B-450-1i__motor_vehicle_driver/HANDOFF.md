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

## 2026-11-27 selected Native/offline checkpoint

Two exact condition A/B constructions and their slower approach fallbacks passed scoped runtime offline checks; all four remained CPU-only (`simulation_started=false`). `native/selected-offline-proof.json` binds four normalized logs to their exact construction hashes. The source contract now marks synthetic fixture rows and seal as diagnostic rather than original Native. Original rail acquisition, public compatibility, saved processing, semantic proposals and independent audits remain pending; status remains partial.

## 2026-11-27 measured parking contract and full branch scope

`measurement-condition_a.json` and `measurement-condition_b.json` bind the current source-joined finalizer to the statute and nearest-rail requirements; a synthetic positive and missing rail-survey negative pass. The finalizer reports a five-second hold separately from the geometric gap and keeps physical-cause confirmation false pending original review. Current inline constructions include an explicit 5 m engineering approach criterion, rather than the runtime default 75 m travel-progress target, and all four were rebuilt and rerun offline.

`native/branch-expansion-plan.json` identifies fourteen exact cases in seven comparison pairs: park, stop, stand, traffic-conflict necessity, other-law compliance, police direction and official-device direction. Only the park pair has offline constructions. The other twelve need distinct Native sources, constructions and all public/saved/audit proofs. They cannot be claimed by the parked trace. Status remains partial.

## 2026-11-27 distinct stop and stand Native plans

The selected offline probe now contains six exact park/stop/stand cases, each with primary and slower-approach fallback. All twelve current constructions passed scoped `runtime.py offline` without starting simulation; `native/selected-offline-proof.json` binds current hashes. The stop request holds 30 frames after approach then requests departure; the stand request holds 130 frames then requests departure. Their diagnostic motion check has two positives and four altered-shape negatives. Actual stop/stand meaning, rail identity and geometry, traffic necessity and authority remain independent original-source review. The eight exception cases lack constructions and proofs. Public compatibility, saved processing, semantic proposals and independent audits remain pending; status stays partial.

## 2026-11-27 first public and saved chain

Condition A primary passed public `runtime.py compatibility` with a generated 600-frame four-camera lossless synthetic fixture. The current receipt is `compatibility/condition_a-primary-compatibility.json`; the missing `original-rail-survey.json` negative was rejected by the finalizer. The public path executed finalization, native validation, conversion, Lean decode, render and final video decode. A fresh materialized diagnostic attempt then passed `runtime.py process-saved`; `saved/condition_a-processing.json` records immutable input hashes, timestamp joins and final decode. These are software proofs only: no original Native rail or legal authority was observed.

The selected parking/stop/stand constructions were rebuilt after the recording description was completed and all twelve exact scoped offline checks passed on those current bytes. Seven comparisons remain planned, with eight exception cases lacking construction. Full selected manifest, the other public and saved proofs, semantic proposals and independent audits remain pending.
