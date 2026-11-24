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
