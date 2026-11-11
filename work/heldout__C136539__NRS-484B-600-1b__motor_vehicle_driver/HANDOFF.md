# heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-600-1b, cell: C136539, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver/assignment.json` (7c767fc5e1a2af136a1f10bb4a63c9966c157107f953fb78fb2c84949dfe481f).

Exact law text: It is unlawful for any person to drive or operate a vehicle of any kind or character at: Such a rate of speed as to endanger the life, limb or property of any person.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- same roadway and person exposure over a fixed physical speed sweep; measured risk to life, limb or property remains a judgment, with no invented legal speed threshold

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 source-bound exposure checkpoint

The frozen evidence inventory lists zero accepted recordings. Four narrow-road pedestrian exposure cases and three controlled comparisons now appear in `case-plan.json`. Requested 2, 5 and 8 m/s values are engineering settings for a physical speed sweep, not legal thresholds; the pedestrian clearance comparison holds the requested 5 m/s setup fixed.

`endangerment_measurement.py` reads original 20 Hz subject and exposed-actor body polygons and velocities, checks identity/frame continuity, and reports speed, surface gap, contact and radial gap closing time. It leaves legal endangerment and stopping-distance judgments null. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver/tests -v` passed four tests, log SHA-256 050cdc8fe793752465a47cc573fe9217dcb1efe153c7b2bd336a7036105e2421. The scoped static gate passed.

Next CPU work: build Native route, participant control, four-camera source capture, source-bound saved finalizer, all exact case constructions/fallbacks, positive/negative compatibility, semantic proposals and independent delivery/comparison audits. Physical speed and participant exposure remain unverified.

The full law also names property. Added two fixed-property clearance cases and a fourth comparison in the same narrow-road cell; all are still planned and require construction/proof.

`exposure_source_capture.py` now captures ordered bottom Native body corners and velocity readbacks for the subject and exposed actor at 20 Hz; it rejects stale frames and retained prior originals. Its source-shaped integration test feeds `endangerment_measurement.py` and passes. Current five-test log SHA-256 fdfb8ebad1c5fecaf60e5e57cb380e6c66e91df7d3670a11bcddc7ce60b6352d. No CARLA route, control or actual exposure outcome has been asserted.

`endangerment_finalizer.py` now checks saved original exposure rows against Native trace and video frame IDs before returning source-hashed observations. Positive, missing-original and stale-trace tests pass; the seven-test log SHA-256 is f7651f367785e7f3bc82680faa637cebb5d80d94d2dc12c66f2fc51d46fe8d69. This is a source-bound saved analysis checkpoint; canonical result writing and runtime compatibility are not yet implemented.

The saved finalizer now writes a derived `exposure_gap_m.jsonl` only from the original body source and builds a canonical Native result shape with physical acceptance flags false; the result passes pinned `native_output.validate_result` in the CPU fixture. Seven tests pass, current log SHA-256 04d2ed549913722914caaf147c6fb2fffef368d07444efe4215dc2eb69c77a16. There is still no full runtime compatibility or physical event proof.

`narrow_exposure_route.py` now selects a connected narrow-road waypoint route using a declared engineering lane-width cap, places the exposed actor on the travel-side verge in either direction, and computes feedback from measured subject position/heading/velocity. Three more tests pass; total ten, log SHA-256 2518ef55259f9a9204753749b33d66cd5f4668413218d399ca6807a875dc3d2a. The route helper is not yet a Native runner, does not prove the participant can spawn at the chosen point, and does not supply four cameras.

## 2026-11-11 first Native construction probe

`native_exposure_probe.py` now lazily runs a narrow-road subject and stationary pedestrian setup, records original 20 Hz Native body polygons, `PipelineCapture` trace/graphs and `FrameMap`, and four synchronized lossless RGB streams. It restores world settings with readback. It is explicitly construction-only and does not seal delivery. The inline `construction-probe.json` passes exact `runtime.py offline` (log SHA-256 5c291e3adf6a6ff3f3160adeee86b1810a8eb83be1604a39af71c02b0d535b74), with no simulation started. Local suite: 12 passing tests, log SHA-256 73e097b6b86f390d14d3092c17023a09c6878f7917251ab129a7b40c4845d3a5. `probe-proof.json` binds the source hash and command.

Physical pedestrian spawn/visibility, scene suitability, subject speed realization and any endangerment judgment remain unverified. CPU work still includes sealing a delivery attempt, six exact cases and tested fallbacks where physical risk warrants, source-bound positive/negative full compatibility, saved processor, semantic proposals and independent delivery/comparison audits.

## 2026-11-11 six-case construction checkpoint

`exposure_case_setup.py` now fixes the six requested engineering settings. `native_exposure_cases.py` constructs a connected 100 m narrow-road route, calls Native spawn for an actual pedestrian or fixed property vehicle, drives a feedback-controlled subject, and captures original subject/exposed body rows and all four camera streams. Person and property near/far placement follows both route directions. A fixed vehicle is a test object representing property; its physical suitability and visibility remain unverified. These are construction probes, not sealed deliveries.

`construction-cases-manifest.json` binds six exact inline constructions under `cases/`. Each exact `runtime.py offline` check passed; logs: `cases/case-offline-clearance_reference.log`, `cases/case-offline-fast_person_exposure.log`, `cases/case-offline-moderate_person_exposure.log`, `cases/case-offline-property_far.log`, `cases/case-offline-property_near.log`, `cases/case-offline-slow_person_exposure.log`. The offline command uses `--python "$PWD/.venv-cpu/bin/python"`; resolving the venv symlink points at the base interpreter and loses Shapely. Local 15-test suite passes, SHA-256 7f1005c2d4fbd51ad23774553312a5cc02e2b2696e7d879ff7074af5f9cffd67.

Next CPU actions: seal a Native delivery attempt for each case with the exact capture command interface, bind the required measurement contracts and diagnostic recipes, run positive/negative compatibility and saved-only processing for each primary and all three distinct physical-risk fallbacks, then semantic proposals and independent audits. Continue strict scoped gate after these proofs; do not mark ready from offline probes.

The six inline constructions were rebound after the case runner gained the runtime `--output-dir` interface and materialized-attempt guard. All six exact offline checks passed again in `.runtime-work/c136539-*-offline-c`; the current `cases/case-offline-*.log` hashes are in `result.json`. The prior `-offline-b` proofs are superseded. `runtime.py capture` has not been run on this CPU host.

CARLA right-of-travel correction: the eastbound right verge is +Y. Both `narrow_exposure_route.py` and `exposure_case_setup.py` now place the exposed body on +Y for eastbound and -Y for westbound, with tested near/far spacing. The original probe and all six inline constructions were rebound and all seven exact offline commands pass on current hashes (`probe-offline.log`, `cases/case-offline-*.log`; SHA-256 in `result.json`). Local 15-test log SHA-256 825e0abe4759685fa242aca047fe1ceaff5eb2f8998d27a570c17b5c03485d04. Earlier construction hashes and offline logs are superseded.

`exposure_comparison_audit.py` now independently reads saved original frame/trace/body sources and the scene receipt for all four planned comparisons. It checks exact case pairs, fixed road identity and engineering settings, the declared difference, exposed kind, and source hashes; missing/changed originals and road geometry are rejected. Seventeen local CPU tests pass (log SHA-256 e5cbbf3f067f1ef04151a7b3c44b762f9a8eeb9971bf8b8dc0f77046c43d683a). The synthetic audit proves checker behavior only; it does not establish actual speed or clearance differences. This script must still be bound into a delivery execution manifest and tested on full saved-processing attempts.
The comparison audit accepts integer road ID zero while requiring a nonzero driving lane; 17 tests rerun, current `cpu-tests.log` SHA-256 e5cbbf3f067f1ef04151a7b3c44b762f9a8eeb9971bf8b8dc0f77046c43d683a.
