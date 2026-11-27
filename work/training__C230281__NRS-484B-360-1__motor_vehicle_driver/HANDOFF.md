# training__C230281__NRS-484B-360-1__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.360(1): A school bus shall not exceed: A speed of 55 miles per hour when transporting pupils to and from school.

Cell: road / travel / school_bus; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 2}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

school bus transporting pupils to or from school on highway; same trip and road Vary only `school_bus_speed` (mph) across [53, 55, 57]. Measure actual bus speed and sourced trip purpose. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Frozen actor/cell do not establish a school-bus driver transporting pupils. Frozen actor is motor_vehicle_driver, while duty belongs to school-bus driver; school-bus identity/trip cannot be presumed from cell control. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## 2026-11-23 saved-source CPU construction

Added `native/measure_speed.py` and `native/source-capture-contract.json` for a 600-frame, 20 Hz, 30-second original frame/Native velocity join and four full-decoded, hashed camera sources. The review must explicitly join the judged motor-vehicle driver to the bus driver, identify the school bus, and cite school-trip purpose and pupil evidence. The checker reports observed mph and frames above the statute's 55 mph figure without supplying a legal verdict. `native/prove_speed.py` passed synthetic 53/55/57 mph diagnostics and eight negative cases (missing motion, broken join, absent pupils, wrong driver, missing join source, stale video hash, invalid velocity provenance and short motion). Fixture velocity is labeled `synthetic_native_sample`; no original observation is claimed. Log SHA-256: `eb0f9af7dc4bfea31b430e36b4a7ce016caa82f416d6212521de5737bef50612`.

The frozen export contains two accepted membership IDs and case titles but no source files or hashes for equivalence review. `case-plan.json.evidence_review` now records that precise gap. Next CPU work is an exact Native construction and selected-case offline/compatibility, saved-processing, candidate, semantic and independent comparison proofs. Actual asset/driver/pupil/trip observations and physical acceptance remain for source review and local execution.

## 2026-11-27 prospective school-bus Native capture checkpoint

`native/bus_capture.py` now authors the exact 53/55/57 mph comparison under the frozen C230281 road/travel/school_bus cell. It requires an original route survey with a source-named school-bus asset, design record, 900 m clear-road estimate, map and spawn; it does not assert that the asset, pupils or school trip have been physically verified. At local execution it requests 600 joined 20 Hz Native velocity/pose/lane rows, four 1920x1080 FFV1 source cameras, current-runtime PipelineCapture, frame decode readback, capture seal and exclusive world restoration. Feedback speed settings are requests; the saved meter measures actual original velocity. `passenger_trip_review.json` must be completed by independent original-source review before the saved meter can report pupil/trip context. Original school-bus identity, pupil visibility, route feasibility, physical speed and legal outcome remain unverified.

The CARLA-free preflight and three focused exact-scope/source-survey tests pass. Runner SHA-256 `cbbcb39ee02d5f3f34093d6692bcab47c2a9813f0defd82ed1a0998f2bffec31`, test log `native/bus-capture-tests.log` SHA-256 `8198f2d4dc29ac9cb5bf8a7540dda0fee3dbf5ee16f270e10e1ce73ea7e1ef56`, preflight `native/bus-capture-check.json` SHA-256 `33b48701b87596aa68c75f9bbe9072a99144b5cc91d59df8daed55154ebdd719`. These are prospective Native preparation, not selected delivery proofs. Next CPU work: bundle the three exact constructions with a source-hashed diagnostic recipe, exercise pinned offline/public positive and missing-source negatives plus recorded-only process-saved, canonical semantic stages, physical/lifecycle fixtures and independent delivery/comparison audits, then run the exact scoped strict gate. Keep `result.json` partial until that passes.

All three exact primary draft bundles now pass pinned `runtime.py offline` with the 53/55/57 case-specific materialized config and CARLA-free Native preflight/tests. Draft manifest SHA-256 `c6cc2ed59a9bf7fff685ceb59c3a8713687eef50f4e27e6ef323f35579f24f2d`; exact construction SHA-256 values: 53 `266cdededf1a95856495fa3c149ec04b6833d740252156476b38d86d625fdb76`, 55 `51ea705d15b92f4788bf9d7ec2218346e4729f334589e0f72bde7987bd037e5f`, 57 `dae97bc03e3be14dd128f7b6dd806d1a7db6745854e4f6c373901f9e502c6fa3`. Returned offline log SHA-256 values: 53 `74655fc2f47e9a6b7517c3a734dbdd7f277e7619cc53b2d3fae3b903ea9b357c`, 55 `ab75f1871e46793ad716e9cd185708ebe7c53b1d2ac8914479c6637ff8b558f3`, 57 `77d7a3ca7a78989653ee3564049ca042594ee901d41b2d4a05c99a2cef736bbe`. The first offline trial failed only because the Python path was relative to the materialized working directory; the rerun used the absolute pinned Python and all three passed. These are unselected diagnostic constructions; public, recorded-only and independent proof chains remain.
