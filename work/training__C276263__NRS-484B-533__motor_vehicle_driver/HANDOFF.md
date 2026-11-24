# training__C276263__NRS-484B-533__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.533. Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 8}. No accepted equivalence receipt was verified.

## Planned controlled comparison

unattended graded stand with engine off, brake set, wheels turned versus omission. Compare only `engine_brake_wheel_triplet` (states) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## Current CPU construction checkpoint

Added exact reference primary draft `draft-grade/reference/primary/construction.json`. `native/grade.py` authors a 200 m road with 4% slope, 3.5 m driving lane and right curb; 4% is a construction choice, not a statutory definition of perceptibility. `native/measure.py` requires source hashes and 600 joined 20 Hz rows of original vehicle, grade, occupancy, and four-camera frames. It demands instrumented engine and front-wheel state, Native parking-brake readback, responsible-person/occupancy observations, and reports state ranges during the unattended interval without a legal verdict or unsupported numeric duty threshold. `native/runner.py --process-saved` fails closed if those original sources are missing.

Pinned `runtime.py offline` passed `runner.py --check` and six full-window tests: a synthetic reference with 500 unattended frames, synthetic-as-original rejection, missing engine sensor, missing wheel sensor, frame mismatch, and changed source hash. Original Native capture was not run. Construction SHA-256 `04a69d0e2023779ac73fc68c511d51adc1094be868403e40af305b81505269b4`; manifest `ee1f2e61f37503c8e551086645448a995e11ff863e8392fd07b82a17ce602acc`; returned offline log `900af8a48cb0e50079b7fe078a01c7f2167051a2eeca6bb6dbc3b710f06530cf`.

Exact remaining CPU work: source-bound review of all eight accepted recording inventories for equivalence and gaps; instrumented Native acquisition for actual engine state, wheel orientation and occupancy/responsible-person departure (CARLA command state alone is insufficient); exact contrast construction and both cases' risk fallbacks; selected-case positive/negative compatibility and saved-path proofs; independent acceptance and comparison audits. The standing interval's purpose, highway public use, perceptibility, and brake effectiveness require original source review. Status remains partial; no accepted recording is replayed or claimed equivalent.

## Contrast and fail-closed Native acquisition checkpoint

The exact reference and contrast primary drafts now bundle `native/capture.py` with 600 Native frames at 20 Hz, four synchronized 1280x720 FFV1 cameras, 4% graded road/curb map readback, vehicle position/velocity, and `carla.VehicleControl(hand_brake, steer)` command plus `vehicle.get_control().hand_brake` readback. Reference requests brake set and steer -0.55; contrast requests brake unset and steer 0. The controller settings are an engineering triplet proposal, not observed front-wheel orientation or engine state. The runner requires an exclusive idle asynchronous world and restores it in `finally`.

The actual capture code explicitly records `engine_source: instrumented_engine_sensor_missing`, `wheel_source: instrumented_front_wheel_sensor_missing`, and `source_kind: occupancy_sensor_missing` with null values. It writes `instrument-review-required.json`. The saved measurement rejects these rather than promoting CARLA control requests, an empty cabin camera, or a case label into engine-off, wheel-direction, or unattended facts. `native/capture.py` SHA-256 `ecbaf9648d3768102a4d64942bc3527198cb30d04e0c98bd86e6a204855acb0a`. The concrete APIs used are `vehicle.apply_control(carla.VehicleControl(...))`, `vehicle.get_control().hand_brake`, `vehicle.get_velocity()`, `vehicle.get_transform()`, `world.get_snapshot()`, `world.get_map().to_opendrive()`, and four `sensor.camera.rgb` callbacks. Additional instrumented sources for actual engine operation, actual front-wheel angle, and attendance remain required; no built-in query for those is asserted here.

Pinned `runtime.py offline` passes on both bundled primaries, including nine unit tests per case (full-window synthetic positive, source/provenance negatives, Native map survey, capture settings, and explicit missing-attendance rejection). Reference construction SHA-256 `ba92616c1d70585e938cc7b0f1916ead4094713e0763ce545b322bfdadba4292`, log `2e1dd1dbc497d0add6185668f4906c51be61370b7904a93999ba8cad00c56985`. Contrast construction SHA-256 `72092e07abc5f8c90f666691c7aa8ba189738bec2f3aa09645fb0d87df9ea375`, log `d53dc152172c9e8a833c036f753e7d38618d6be6d5a880a42e1a1131abcecdef`. Draft manifest SHA-256 `5abebb81af8df1d57b0f89186368301e33c0d8405fd713603a17cd8fe2bf89a2`.

`accepted-evidence-review.json` joins all eight accepted membership IDs to the frozen review context. Each row has zero receipt sources, so no source-hashed equivalence is established; review SHA-256 `856166602a1d77c0f71d80a90fc678340e6b3be7e7be181e850cbbbb3542a38b`. No accepted original is replayed. Remaining CPU work: acquire/review original instrumented engine, wheel and attendance sources or a reviewed equivalent receipt; complete selected-case compatibility/saved finalization, physical-risk fallbacks, independent audits and comparison. Physical execution and legal judgment remain local. Status partial.
