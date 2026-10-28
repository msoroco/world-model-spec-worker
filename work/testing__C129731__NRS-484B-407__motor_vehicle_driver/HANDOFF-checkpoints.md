# testing__C129731__NRS-484B-407__motor_vehicle_driver

Status: **partial**. All six preparation responsibilities have authored artifacts and executable CPU-checked components; this is not first-run readiness.

Exact law, cell, actor, witness, summary and existing evidence are preserved in the hashed input and case plan. Relevance, law template, bindings, value-free judgment requirements, canonical cases and constructions are under proposals/ and constructions/. No historical observation is claimed as current evidence.

Cases and comparisons: testing__C129731__NRS-484B-407__motor_vehicle_driver__baseline: Neutral definition retained and not selected by default.; testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_below: 500-foot two-approach visibility probe; desired horizon must be measured. Station-to-horizon calibration is outstanding, never infer achieved distance.; testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_at: 500-foot two-approach visibility probe; desired horizon must be measured. Station-to-horizon calibration is outstanding, never infer achieved distance.; testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_above: 500-foot two-approach visibility probe; desired horizon must be measured. Station-to-horizon calibration is outstanding, never infer achieved distance.

The root construction is the first non-baseline case anchor. Additional canonical case proposals (each contains its own config.json and identical implementation/map/camera files):

- constructions/testing__C129731__NRS-484B-407__motor_vehicle_driver__baseline.json
- constructions/testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_below.json
- constructions/testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_at.json
- constructions/testing__C129731__NRS-484B-407__motor_vehicle_driver__sight_above.json

Runner: `/usr/bin/python3.11 work/testing__C129731__NRS-484B-407__motor_vehicle_driver/runner.py --check`. Later native Python 3.8+ launch accepts `--output-dir PATH --host HOST --port PORT --case-id ID`; its runtime imports remain lazy. It owns the generated world settings and spawned actors, never the simulator server. Baselines require explicit --include-baselines. The already-created executor output directory is allowed; attempt/capture files are exclusive.

Original capture uses runtime/python/PipelineCapture immediately after each tick, with camera queues joined by exact CARLA frame. Saves native graph/evidence, recorder additional data, road, full trace, four RGB sequences and frame map. Missing mandatory projections emit null and a missing-capability reason, never targets as observations. The runner deliberately returns failure until all required setup/capture/video checks are implemented and measured.

Measured finalization: retain failed attempt and hashes; implement missing atom/cause projections, then execute each frozen setting once. Recompute summaries with `finalize.py OUTPUT --channel NAME --start T0 --end T1 --statistic mean` using actual saved sample times; match the frozen method/window/statistic, keep raw streams, validate both approach horizons/footprints and all original frames, encode and inspect full-trace camera review videos with frame map, and compare requested versus measured quantities. A diagnostic summary does not authorize endpoint changes, extra sweep points, legal thresholds, or acceptance. Repair the implementation at the same setting under a new retained attempt if realization fails. Physics-dependent ranges remain explicitly incomplete and need feasibility evidence before freezing.

Runtime/implementation uncertainties and remaining work:

- No CARLA execution: spawn inventory, road import, collision/departure, controller tracking and camera visibility unverified.
- Mandatory raw atom streams are implemented only for direct telemetry; remaining atom projections require completion against retained original-frame PipelineCapture evidence.
- Primary encoded review videos are not implemented; runner saves four synchronized original RGB PNG sequences and exact frame map.
- The crest exists in authored elevation profile but paired sight targets need a calibrated inverse station-to-nine-point-horizon mapping before first-run readiness.
- U-turn footprint containment and incoming native route search coverage for every frame need stronger static certification; route endpoints alone do not prove sight coverage.

Summary/text conflict: No direct textual contradiction detected; witness/summary facts remain proposals, not observations.

No CARLA run, statutory judgment, physical acceptance or human-review blocker is claimed. Update 002 applied; continue does not release any future pause.

## Update 003 continuation

Status: **externally blocked**, with implementation gaps replaced by executable code. `measurements.py` projects every mandatory channel from original native map/actor/device/raycast observations; unavailable observations raise errors. Native yield205 signals with validity and native crosswalk objects with explicit outlines are authored in road.xodr and read back from the generated world. A missing native device/crossing cannot pass setup.

Shared Recording owns four actual VP9 WebM encoders and original-frame PipelineCapture. Shared contracts validate all channel samples, encoded frame counts/rate, contexts, participant histories, full footprint containment, measured target checks and original-window summaries. Resource cleanup attempts every owned action. The runner has a genuine successful return path through validate_output, as well as retained failure reports. Synthetic successful/failed output fixtures with real encoded video exercise the contract and do not establish physical feasibility.

The historical partial paragraphs above describe the earlier checkpoint. The current external requirements supersede those implementation-gap lists:

- {"category": "live_measurement", "evidence": "No native CARLA raycast/mesh observations exist. road.xodr crest and measured nine-point projection are implemented; desired station choices are not physical feasibility evidence.", "next_action": "Run declared static native setup calibration retaining geometry/rays; freeze justified stations before case execution, update exact deliberate differences and source provenance without inventing legal thresholds.", "requirement": "Establish physical station-to-two-approach sight-horizon mapping for the frozen 147.4/152.4/157.4m probes and complete every-frame search extent.", "requires_live_execution": true}
- {"category": "live_measurement", "evidence": "No simulator available. Success and failure contract fixtures check software behavior only, not physical feasibility.", "next_action": "Execute each frozen non-baseline case once; retain failed attempts and repair actual causes at the same setting; recompute original measurement windows and validate outputs.", "requirement": "Confirm native maneuver completion, physical footprint containment, target tracking and original RGB/graph capture for the frozen cases.", "requires_live_execution": true}

Case bundles inline shared sources with `source` provenance and include all runtime dependencies plus case-plan.json. Lead shared materializer runs every case bundle before its offline suite; source hashes and exact logs are in result.tests and materialized-tests.json. Update003 is continue and does not release a future pause. No simulator was launched.

Final lead corrections: participant histories join original actor IDs in requested order; original packet relations and exact native nine-body visibility schema are consumed. Each native incoming lane must have an unambiguous230m route even if an earlier blocker ends horizon scanning. The U-turn entire swept body has an analytic lateral-amplitude bound plus721 intermediate poses and a runtime check using actual native extents. Scalar sight horizons, truck widths and backing-overlap histories are saved separately and summarized over explicit original sample windows with min/min/max statistics. Generic lack of a simulator is a runtime uncertainty, not a preparation blocker. Only the following assignment-specific external requirements determine blocked status:

- {"category": "live_measurement", "evidence": "No native CARLA raycast/mesh observations exist. road.xodr crest and measured nine-point projection are implemented; desired station choices are not physical feasibility evidence.", "next_action": "Run declared static native setup calibration retaining geometry/rays; freeze justified stations before case execution, update exact deliberate differences and source provenance without inventing legal thresholds.", "requirement": "Establish physical station-to-two-approach sight-horizon mapping for the frozen 147.4/152.4/157.4m probes and complete every-frame search extent.", "requires_live_execution": true}
