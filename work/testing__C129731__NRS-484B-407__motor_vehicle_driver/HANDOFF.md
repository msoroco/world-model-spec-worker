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
