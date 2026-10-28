# testing__C215286__NRS-484B-113-2__motor_vehicle_driver

Status: **blocked by the specific external requirement below**. Implementable preparation code is complete; no simulator was launched and no physical or legal acceptance is claimed. Update003 is acknowledged; no pause is active.

Exact law/cell/actor/witness/summary and existing evidence are preserved by the input hash in result.json and sources in case-plan.json. Heavy actors remain heavy_vehicle_driver. Draft template, relevance, bindings, judgment requirements and canonical cases are under proposals/. Subject outcomes remain measured hypotheses and judgment phrases have no adopted thresholds. Baselines are retained but not selected by default.

Implemented: authored OpenDRIVE roads/junctions/crest, native yield205 signals with lane validity or native crosswalk objects where needed; pure-pursuit path and bounded speed/reverse/gap controllers for all participants; exact original-frame PipelineCapture; four real VP9 WebM encoders; mandatory measured native actor/map/device/raycast projections; participant/body histories, collision checks, full route containment, observed target checks and recomputable raw scalar summaries. Resource cleanup attempts capture, encoders, every actor/sensor, signal handlers and world settings independently, and never stops the simulator server. The runner has genuine success and retained diagnostic failure paths through strict validate_output.

Visibility requires every declared native incoming lane to extend230m on every original frame, exact any-of-nine body-ray horizons, no route-limit censorship, and both through-road approaches for yield cases. The whole U-turn swept footprint is bounded analytically and checked at721 intermediate poses, then checked against actual actor extents. Scalar methods/windows are frozen in config.measurement_definitions; original raw streams and actual sample_window_s are retained.

Use `/usr/bin/python3.11 work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/runner.py --check` offline. Later native Python3.8+ invocation is `runner.py --output-dir PATH --host HOST --port PORT --case-id ID` with supplied runtime/python on PYTHONPATH. An existing executor-created output directory is allowed; attempt/capture files are exclusive. Native assets/dependencies are queried before evidence acceptance.

Cases and isolated comparisons:

- testing__C215286__NRS-484B-113-2__motor_vehicle_driver__baseline: Neutral definition retained and not selected by default.
- testing__C215286__NRS-484B-113-2__motor_vehicle_driver__outside_crosswalk_reverse: Backing remains entirely upstream of marked crossing; no street-corner maneuver.
- testing__C215286__NRS-484B-113-2__motor_vehicle_driver__over_crosswalk_reverse: Same reverse controller requests crossing footprint overlap; no street-corner maneuver.
- testing__C215286__NRS-484B-113-2__motor_vehicle_driver__outside_intersection_reverse: Straight backing stays downstream of the authored native junction; no street-corner maneuver and no crosswalk overlap.
- testing__C215286__NRS-484B-113-2__motor_vehicle_driver__into_intersection_reverse: Identical straight reverse controller crosses road 2 into native junction connector 11, with observed footprint against authored intersection bounds; no street-corner maneuver.

The root construction.json anchors testing__C215286__NRS-484B-113-2__motor_vehicle_driver__outside_crosswalk_reverse. Each additional canonical proposal below includes its own config and the same implementation/map/cameras; shared files carry work/_shared source provenance:

- constructions/testing__C215286__NRS-484B-113-2__motor_vehicle_driver__baseline.json
- constructions/testing__C215286__NRS-484B-113-2__motor_vehicle_driver__outside_crosswalk_reverse.json
- constructions/testing__C215286__NRS-484B-113-2__motor_vehicle_driver__over_crosswalk_reverse.json
- constructions/testing__C215286__NRS-484B-113-2__motor_vehicle_driver__outside_intersection_reverse.json
- constructions/testing__C215286__NRS-484B-113-2__motor_vehicle_driver__into_intersection_reverse.json

Validation: all 12 materialized-bundle commands and the two owner commands passed. The40-test assignment suite includes successful and failing full output fixtures with real encoded video, every mandatory-channel/null rejection, timestamps, target/physical-cause mismatch, contexts, participant history, route/footprint departure and independent cleanup failures. Synthetic fixtures prove software contracts, never physical feasibility. Exact commands, exits, logs and source hashes are in result.tests; materialized-tests.json records each proposal hash and confirms materialization preceded tests.

External requirement (missing implementation is not classified as an external barrier):

- {"category": "external_asset", "evidence": "OpenDRIVE object construction, native geometry gate and full encoded evidence are implemented. This repository contains no CARLA generator/rendering assets or verifiable native crosswalk inventory.", "next_action": "Supply a supported native map/crosswalk asset or verify generator support using the declared crosswalk object; preserve both intersection/crosswalk branch pairs.", "requirement": "A native CARLA generator/map must supply the rendered crosswalk asset corresponding to the authored crosswalk object and its get_crosswalks polygon.", "requires_live_execution": true}

Measured finalization: supply the listed native asset or retained static native calibration evidence, then freeze any approved physical binding changes with exact source provenance. Execute each frozen non-baseline setting once, retain original graphs/road/recorder/trace/videos and failed attempts, inspect native feature rendering and physical cause, recompute declared summaries from saved scalar samples, and run validate_output. For requested physical target failure, diagnose and change the cause at the same setting under a new retained internal attempt. Do not add sweep points, shift endpoints, silently alter comparison conditions or infer legal standards. Source-summary conflicts remain in case-plan.json; notably the truck summary supplies no lawful numeric overtaking-duration bound. Previous preparation checkpoint notes are retained separately in HANDOFF-checkpoints.md.
