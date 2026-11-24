# testing__C111125__NRS-484B-307-3a__motor_vehicle_driver

Status: partial construction and comparison checkpoint. Four exact cases and three controlled comparisons are proposed; no physical recording or legal outcome is claimed.

## 2026-11-24 CPU construction checkpoint

`native_attempt.py` now runs one synchronous 20 Hz Native attempt for an exact dual-green case. It applies the caller's controller before each world tick, checks consecutive snapshot frames and 0.05-second timestamps, samples actual ego/other-user positions, and requires per-frame original lamp packets keyed to the surveyed official head and facing approach. Other-user frames require original source-hashed lawful-use packets; their legal meaning remains unresolved. It retains `original-events.json` plus `native-attempt.json` with a source hash and an explicit `physical_acceptance_claimed: false` value. The caller still must supply the independently observed lamp packet source, actual Native controller, and four-camera capture.

`saved_attempt.py` reads the sealed event source without CARLA, verifies event hash, exact case identity and 20 Hz frame sequence, then independently opens every lamp and lawful-use packet by path and hash and matches its content to the saved row. It delegates geometric region measurement to `dual_green.measure_original` and returns no permission or right-of-way verdict. A fixture with a fake world exercises both paths; it is a software proof only. No actual dual-lamp hardware or CARLA map has been observed in this package.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-3a__motor_vehicle_driver/tests -v` passed 13 tests in `cpu-tests.log` (SHA-256 `ec9449029cd14b1c8e9b00ba4198b6c58bbb0756041313e4fa91409917a6806b`). `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-3a__motor_vehicle_driver --complete` passed in `cpu-static-check.log` (SHA-256 `5601395d92c07209815f2cfec5db3b3b3a3089665173414d09191a641e5c136d`). The same exact assignment command with `--require-delivery-ready` failed in `cpu-strict-check.log` (SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`) because status remains partial.

Exact law: NRS 484B.307(3)(a) — Where the signal is circular green with a green turn arrow: Vehicular traffic facing the signal may proceed to make the movement indicated by the green turn arrow or such other movement as is permitted by the circular green signal, but the traffic must yield the right-of-way to pedestrians lawfully within an adjacent crosswalk and to other traffic lawfully using the intersection at the time the signal is exhibited. Drivers turning in the direction of the arrow when displayed with the circular green are thereby advised that so long as a turn arrow is illuminated, oncoming or opposing traffic simultaneously faces a steady red signal.
Assigned branch(es): Other movement permitted by circular green.
Cell: C111125 (intersection, straight, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Bind an actual Native map and official dual-aspect head survey, applicable straight-movement restrictions, crosswalk geometry and source hashes to `dual_green.check_site`. CARLA Green state alone cannot verify a simultaneous arrow lamp. Confirm original aspect observation sources for every frame and preserve any lawful-use uncertainty.
2. Build the exact runner/config/construction, per-case bundles, 20 Hz capture and case-specific saved finalizer. Author canonical semantic proposals and selected-requirement measurement contracts. Keep the assigned straight movement while circular green and the turn arrow face ego.
3. Run per-case offline and positive/negative compatibility proofs, saved-only processing and independent delivery audits. Add one or two fallback constructions only if a concrete measured risk justifies them; test each fallback. Current physical-risk assessments identify potential dual-lamp visibility risk but no fallback is claimed.
4. Rerun the assignment strict gate and keep status partial until it passes.

## Exact case and comparison mapping

`case-plan.json` lists `dual_clear`, `dual_vehicle_present`, `dual_pedestrian_present`, and `dual_pedestrian_late`. These compare vehicle presence, pedestrian presence, and location at first dual-green exhibition, respectively. The fixed straight route, facing head, arrow direction, map/crosswalk survey, camera plan and duration are enforced by `comparison_audit.py`. `dual_green.py` source-gates the site, creates Native actors lazily, and measures original frame order, both lamp aspects, ego intersection entry, and other-user region. It leaves straight-movement permission, lawful use and right of way for source-backed review rather than deriving a verdict.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-3a__motor_vehicle_driver/tests -v` passed 9 tests; see `cpu-tests.log` and its SHA in `result.json`. The tests include wrong-arrow, sole-circular-green, missing lawful-use source, route bend, source mutation, Native actor cleanup, and comparison negative paths. `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-3a__motor_vehicle_driver --complete` passed static validation (`cpu-static-check.log`). The same command with `--require-delivery-ready` failed as expected because this package remains partial (`cpu-strict-check.log`). This is unfinished CPU work, not an external blocker.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 four-camera source audit checkpoint

`native_attempt.py` now accepts a per-tick camera callback and retains four original PNG byte streams with path and SHA-256 references in `original-cameras.json`; it binds that manifest to `native-attempt.json`. `camera_audit.py` independently reopens and fully decodes each referenced PNG, verifies exact camera names and 1920×1080 overview plus three 1280×720 detail dimensions, enforces one distinct source per view/frame, and joins each source to the sealed original event frame identity and timestamp. `saved_attempt.measure_delivery` requires the 900-frame 20 Hz production duration and the four-camera audit; its receipt explicitly leaves physical visibility and legal outcome unconfirmed. Small 2×2, three-frame fixtures exercise success, missing image, changed frame identity and production-duration rejection.

The focused command `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-3a__motor_vehicle_driver/tests -v` passed 17 tests in `cpu-tests.log`. The scoped `worker_check.py --assignment testing__C111125__NRS-484B-307-3a__motor_vehicle_driver --complete` passed; adding `--require-delivery-ready` still rejects the truthful partial status. Original source-bound site and signal survey, complete per-case fixtures/proposals, offline/compatibility proofs, and saved delivery receipts remain CPU preparation work.

## 2026-11-24 saved contrast checkpoint

`saved_attempt.check_case_observation` now checks each exact case against the first observed dual-green frame. It rejects a user in the clear case, the wrong user kind or region in present cases, and a late pedestrian who never actually enters the adjacent crosswalk after exhibition. These are geometric comparison checks; they do not infer lawful use, right of way or legal permission. The focused suite passed 20 tests (`cpu-tests.log`, SHA-256 `b704dd1155b0f10362d8a958698cfe6ec622ec8bbc5b4ff613ecdfa53a5c5894`). Complete per-case diagnostic/compatibility, semantic and saved delivery preparation remains to be built before readiness.

`dual_green.measure_original` also requires the first simultaneous dual-green observation before ego intersection entry and uninterrupted observation through entry. A late onset or missing aspect at entry is rejected. The focused suite now passes 21 tests (`cpu-tests.log`, SHA-256 `5d0c3eef4b03464acde0538bbdadd15d6fdf3942e40ce63718079645c8e49850`).

## 2026-11-23 measured straight controller checkpoint

`native_straight_controller.py` now supplies the callback required by `native_attempt.py`. It reads the surveyed straight route and live ego pose/velocity, commands throttle and steering toward the route, and brakes at its endpoint. It checks exact tick order, actor identity, finite motion and route departure. For a present other user, it requests an engineering stop while that actor occupies the surveyed intersection or adjacent crosswalk; this does not establish lawful use, right of way or legal yielding. `for_exact_case` binds each of the four case IDs to the expected actor count and kind. CARLA imports remain lazy.

The focused suite passed 26 tests, including source-tamper, controller stop, route-departure and exact-case rejection checks. Pinned `runtime.py preflight` and scoped static `--complete` passed. Exact scoped strict `--require-delivery-ready` exited 1 on truthful partial status. The exact command/log SHA-256 records are in `result.json`. No `execution-manifest.json` exists for this package yet, so pinned `runtime.py offline` cannot be invoked for a selected construction; authoring exact bundles and that manifest remains an actionable CPU task.

Next CPU work: integrate the controller with surveyed Native scene and four-camera lifecycle; author four exact inline constructions, diagnostic recipes and selected-requirement finalizers, then run pinned offline, positive/negative compatibility, saved processing and independent delivery audits. Build source-grounded semantic proposals and risk-tested fallbacks where measured physical risk justifies them. Original dual-aspect lamp/site evidence and pixels remain unverified.
