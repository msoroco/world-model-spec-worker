# training__C405647__NRS-484B-267-2c__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.267(2)(c); with 484B.267(4): Upon approaching an authorized emergency vehicle or an official vehicle of a regulatory agency which is moving or preparing to move in any direction, including, without limitation, arriving at or leaving the scene of a crash or other incident, and making use of flashing lights meeting the requirements of subsection 3 of NRS 484A.480 [DEF-NRS-484A-480-3], the driver of any other vehicle shall, except when otherwise directed by a law enforcement officer: Be prepared to stop. As used in this section, “preparing to move” means any indication that is visible to an approaching driver that an authorized emergency vehicle or an official vehicle of a regulatory agency is about to move, including, without limitation: (a) A movement of the vehicle; or (b) The use of hand signals by the driver of the vehicle.

Cell: road / travel / emergency_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

qualifying emergency/official vehicle moving or visibly preparing to move with required flashing lights; no officer direction Vary only `ego_stop_preparedness` (category) across ['braking_capacity_available', 'not_available']. Record native light state, emergency vehicle movement/hand signals, ego approach, deceleration capability and reaction. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Be prepared to stop is qualitative; model braking readiness does not decide legal meaning. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## 2026-11-23 saved-source approach construction

Added `native/measure_readiness.py` and `native/source-capture-contract.json`. The checker requires 600 original joined 20 Hz motion samples and all four decoded, hashed camera streams. It binds independent review of qualifying vehicle class, referenced flashing-light requirements, visible motion/hand-signal indications and officer direction to the saved cameras. It reports actual approach gap, brake delay, stop distance and deceleration as engineering observations without deciding what “prepared to stop” means legally. `native/prove_readiness.py` passed synthetic braked/unbraked diagnostics plus nine rejections: missing trace, bad frame join, no flashing, no approach, stale camera hash, wrong vehicle class, unreviewed visibility, unsourced lights and wrong Native provenance. Fixture motion is `synthetic_native_sample`, never original CARLA velocity. Log SHA-256: `208a6c9b87241270f8598cac6b495bdaad34408497845042639a25d0a5c36c0c`.

`case-plan.json.branch_gap_review` identifies separate movement/hand-signal and officer-direction branches still to plan. Next CPU work is exact Native construction, selected cases and current-runtime offline/compatibility, saved-processing, candidate, semantic and independent comparison proofs. Source qualification, physical realization and legal judgment remain unverified.
