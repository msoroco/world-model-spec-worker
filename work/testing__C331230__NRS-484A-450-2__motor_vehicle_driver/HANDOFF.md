# Partial executable preparation: NRS-484A-450-2

Status: partial. This is an executable draft, not accepted first-run readiness. No CARLA run or legal/physical acceptance is claimed.

The exact assignment law, cell, actor, witness contexts, summary, timing, exceptions and existing evidence were reviewed. Consumed source paths and hashes are in case-plan.json. Generated draft relevance, law template, value-free judgment requirements, bindings and cases are under proposals/. Review status remains draft. Summary stop-duration/epsilon language is not adopted as a legal minimum.

Cases: testing__C331230__NRS-484A-450-2__motor_vehicle_driver__baseline, testing__C331230__NRS-484A-450-2__motor_vehicle_driver__halt, testing__C331230__NRS-484A-450-2__motor_vehicle_driver__no_halt. The baseline is retained and unselected. case-plan.json explains linked comparisons and their sole deliberate differences. Cases alter controller targets only; subject_behavior remains null until observed. Incomplete judgment sweep specifications name the missing physical inputs and remain unlabeled.

Executable files: runner.py lazily imports CARLA, authors the OpenDRIVE road and physically controls ego and relevant participants using bounded feedback. scenario.py selects the case-specific route and computes actual footprint gaps and approach/exit observations. The runner records four original RGB image streams, PipelineCapture native graphs/recorder/map/trace, exact camera-frame joins, physical_samples.jsonl, and requested raw-channel streams at 20Hz. Unsupported atom projections are explicitly null, never filled from targets. Collision capture, signal termination and independent actor/settings cleanup are implemented. Lane-change uses a right indicator for its rightward transition and an authored one-way two-lane approach.

Offline usage from repository root: `python3.11 work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver/runner.py --check`; `python3.11 -m unittest discover -s work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver/tests`. Live usage later: `python3.8 runner.py --output-dir PATH --host HOST --port PORT --case-id ID` with repository runtime/python and its dependencies available. An existing empty executor output directory is supported; preserve prior attempts. Never start/stop the simulator server from this package.

construction.json anchors the first target case. Every other target has a canonical proposal with its own inline selected config: constructions/testing__C331230__NRS-484A-450-2__motor_vehicle_driver__no_halt.json. Linked runner, scenario, map and capture implementations are identical.

Offline evidence is stored in result.tests and result.lead_tests, including exact commands, exit codes, log hashes and tested implementation hashes. CPU tests cover feedback braking/saturation/wrapped heading, comparison isolation, whole-footprint authored-surface checks, target measurement disagreement, missing capture, null mandatory channels and broken frame joins. These tests use synthetic geometry/records and do not establish simulated physics.

Remaining preparation gaps:

- Per-atom JSONL projection, exact law-specific setup validation and physical-cause target checks remain unimplemented; raw capture alone is insufficient.
- Physical stop-sign governed lanes and near-side unmarked crosswalk derived from rendered sidewalk boundaries require native validation; reference OpenDRIVE signals do not prove rendered native devices.
- Summary duration/epsilon is not in exact law; retain raw cessation samples and do not adopt a legal minimum duration.
- Law-specific controller branches and raw geometry are implemented; map/device governance, full mandatory atom projections and physical feasibility remain unconfirmed.
- Primary encoded synchronized review videos remain to be produced from retained original RGB images.
- First-run spawn/asset availability, native Python 3.8 imports, client/server readback, controller tracking, camera framing, actual geometry and emitted indicators remain unverified.

Measured-results finalization: retain the original run and use `python3.11 finalize.py OUTPUT_DIR` to check trace/video joins, rates, mandatory-channel completeness and capture artifacts. Null streams must fail. Resolve missing projections against original raw geometry/device/participant evidence; never substitute requested targets. Recompute target checks and any declared scalar statistics from actual saved windows, retain full trace and physical-cause evidence, audit rendered governed features and produce full synchronized review videos. For judgment ranges/durations, first obtain a separately identified physical feasibility episode, document measured feasible bounds and engineering spacing, freeze the resulting case grid before original selected executions, and preserve all endpoints/interiors and failures. Do not infer a legal standard, add points after outcomes, or retry unchanged attempts. Remaining law-specific integration must be completed before status can become ready. Update 002 acknowledged; any pause persists until explicit resume.
