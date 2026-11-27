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

## 2026-11-27 exact scene and camera profile

`native/scene.py` now writes two exact requests under `native/requests/`, bound to a worker-authored 200 m OpenDRIVE driving lane and shoulder. Both use the active four-view 20 Hz / 30 s capture profile; only requested ego brake response varies. `native/test_scene.py` passes exact-pair and changed-map/motion/light rejection tests. `native/measure_readiness.py` and its source contract now require the same four camera names (`overview`, `approach`, `reference_corner`, `driver_reference`). The saved-source diagnostic reran successfully with nine source/review negative cases. This is a construction hypothesis and synthetic diagnostic, not observed vehicle qualification or delivery acceptance.

Next: implement lazy Native capture/controller for the exact requests, produce source-bound offline and positive/negative compatibility bundles for selected cases, then saved processing and semantic/independent comparison audits. The current `result.json` correctly remains partial.

The lazy `native/runner.py` passes CPU preflight for both saved exact requests without importing CARLA. Its physical path requires an empty `.runtime-work/` capture directory and exported `SCENARIO_PIPELINE_OUTPUT_ROOT` there, checks an exclusive idle CARLA world, generates the authored OpenDRIVE road, records original Native poses and four lossless frame-joined camera streams, and restores the prior world. The runner does not claim that requested flashing lamps satisfy the statute; original pixel and source qualification review remain required. The saved-source checker now checks per-camera original dimensions against the active 1920×1080 overview plus three 1280×720 views.

`native/from_original.py` converts original frame-joined Native actor poses, body vertices and brake requests plus explicit per-frame original-pixel review into the saved approach trace; it rejects stale review frame joins and synthetic motion provenance. Focused scene/conversion tests now pass three cases. The review itself and physical recordings are not present.

The acquisition controller now requests a 5 m/s cruise ceiling before the emergency response, keeping the 30 s unbraked contrast on the authored 200 m road; the brake-ready case requests 0.8 brake from frame 180. These remain requested settings, not measured Native trajectories. Both regenerated exact request hashes and CPU preflights pass.

Each regenerated request now includes a physical risk assessment for road extent, four-view lamp/motion visibility, statutory vehicle/lamp qualification and the limits of brake response as a legal proxy. These are requested construction risks, not observed outcomes. The latest two request preflights, focused tests and scoped partial check pass.

## 2026-11-27 independent source-bound comparison

`native/audit_comparison.py` recomputes the two 600-frame saved observations from original-shaped sources, checks each bound exact Native request, verifies fixed scene settings, full emergency trajectory, indication and reviewed trigger context, and requires the measured brake-response contrast. `native/prove_comparison.py` passes a synthetic positive and rejects a wrong request, stale reported observation, changed emergency trajectory at and after the trigger, changed reviewed class or officer direction, and absent brake contrast. This is a software fixture, not physical or legal acceptance. Proof: `native/comparison-proof.log` SHA-256 e58c1dccf23442e52e769fd779ceb3dead47a067b1c0dd28af12d3a9d8a6ac3f.

The lazy physical runner now seals `native-request.json` beside its capture sources for later independent comparison. Exact selected offline/public compatibility, semantic stages, full source branches and delivery audit remain CPU work; status stays partial.

The saved meter also reports the number and fraction of approaching frames with observed brake readback after the trigger, preserving a continuous-response engineering observation without imposing a legal stopping threshold.

The focused conversion test now exercises `from_original.process` end to end on 600 original-shaped Native rows under `.runtime-work/`, confirms the produced trace, and rejects a missing actor source. The rows are synthetic test values; original CARLA capture and independent pixel review remain unperformed. Scene/conversion test log SHA-256 `2d51d47ee743889ca5d48b6d66a17f12e0132f35c5f52a0c9f33388b13bfd48c`.

`case-plan.json.source_observation_mapping` now names the concrete Native, saved and camera channels for all eight source terms. It explicitly leaves original capture, statutory vehicle/lamp qualification, actual visibility and the officer-direction exception unverified. This is a source-to-channel plan, not an accepted evidence mapping.
