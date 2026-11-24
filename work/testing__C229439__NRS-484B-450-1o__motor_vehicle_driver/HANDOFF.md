# C229439 / NRS 484B.450(1)(o) motor vehicle driver

Status: **partial**, pending CPU delivery package. The exact strict assignment check fails because this result is partial. No accepted recording exists in the frozen evidence inventory. The conditional witness does not prove the sign's exact instruction, official authority, governed area, or effective conditions. No external blocker has been demonstrated.

## Source and coverage

The exact law prohibits stopping, standing, or parking a vehicle at a place where an official traffic-control device prohibits that act, except when necessary to avoid conflict with other traffic or in compliance with law or a police officer's or official device's direction. It contains no numeric threshold or judgment sweep for this assignment. The C229439 cell is a road parking maneuver with a generic parking-restriction device; the generic device category does not establish a prohibition. `case-plan.json` cites the frozen assignment, witness, evidence inventory and topic source by SHA256. Its evidence review records the absence of accepted recordings.

The eight planned exact cases are `park_effective`, `park_not_effective`, `stop_effective`, `stand_effective`, `stop_for_conflict`, `park_law_direction`, `park_police_direction`, and `park_device_direction`, each prefixed by the assignment ID plus `__`. Five controlled comparisons hold the source road, route, vehicle and capture profile fixed while varying effective time or one exception cause. The three halt verbs have separate device instruction requirements. Every case has a physical-risk assessment for sign/footprint visibility. These are planned recordings, not Native executions or accepted evidence.

## Implemented CPU construction and checks

`parking.py` takes source-hashed JSON site/device/driver references. It rejects missing official placement, traffic-purpose, legal-consistency and authority records, incorrect governed polygons, and wrong vehicle/driver source fields. `construct_case` invokes a lazy Native adapter for map readback, exact sign instruction readback, driver spawn, parking route, and exception-cause configuration. The injected adapter is a contract exercised by a fake in tests; a concrete CARLA adapter remains CPU work. `execution-manifest.json` binds eight exact materialized constructions with source hashes. Each passed the pinned `runtime.py offline` command; `proof-*.log` and bound SHA256 values show the results. These offline runs exercise the exact configuration and adapter fixture but do not run CARLA.

`measure_original_history` checks original contiguous 20 Hz rows, actor and device identity, source device state, full body footprint inside the governed polygon, actual halt activity, velocity and independently sourced exception conditions. It returns counts and `legal_judgment: null`. `audit_saved_attempt` independently validates 900 source rows, frame-map joins, all four camera source hashes and profiles; it leaves full video decode/pixel review for the pinned media auditor. `audit_comparison` rejects fixed-condition changes or missing declared differences. `finalizer.py` performs saved-only source-hashed processing and writes observation results only after the 900-frame audit passes; the test rejects a tampered source without producing a result. These checks cannot establish physical sign legibility or legal validity.

The focused command `.venv-cpu/bin/python -m unittest discover -s work/testing__C229439__NRS-484B-450-1o__motor_vehicle_driver/tests -v` passed 13 tests; `cpu-tests.log` and its SHA256 are in `result.json`. `.venv-cpu/bin/python runtime.py preflight` passed with pinned Lean 4.28.0. The exact `worker_check.py --assignment testing__C229439__NRS-484B-450-1o__motor_vehicle_driver --complete` passed static checks (`checkpoint-check.log`). The same command with `--require-delivery-ready` failed at `Preparation acceptance failed: partial/missing packages remain` (`strict-check.log`), consistent with the partial status.

## Next CPU work

1. Implement the concrete lazy CARLA adapter and original context acquisition/readback. Bind each case to its exact configuration, construction JSON, required source packets, measurement contract and four-camera 900-frame capture plan. Run the pinned atom preflight.
2. Author canonical semantic stage proposals and semantic index for the eight planned cases. Keep legal-consistency and exception necessity for source review, without inventing a verdict.
3. Add case-specific diagnostic recipes and run pinned positive/negative `runtime.py compatibility` and `runtime.py process-saved` for each case. The eight exact `runtime.py offline` proofs and the independent saved-only source finalizer are implemented; the pinned converter, decoder and renderer path is still pending.
4. Bind tested delivery and comparison audits in every manifest entry, including full pinned media decode and actual-pixel review of later Native evidence. Add risk-based fallback constructions only after a concrete primary motion/camera failure trigger is established.
5. Recheck every exact case and comparison against the statute and contracts, then run the assignment strict gate. Mark ready only when it passes.

The later GPU work is actual vehicle motion, sign and context visibility, 20 Hz camera coverage and physical capture review. These do not excuse the remaining CPU items above.

## 2026-11-23 saved media checkpoint

`saved_media_audit.py` independently checks source-hashed Native rows and frame map, 900 contiguous 20 Hz identities/times, four source-hashed original PNG archives, ordered frame members, per-frame pixel SHA bindings, profile dimensions, and full PNG decode of all 3,600 images. The default profile is 1920x1080 front and 1280x720 for rear/left/right. It returns no physical or legal acceptance. The focused test uses a 2x2 synthetic image override and proves that the default profile rejects that fixture; it also corrupts a source-hashed row pixel binding and proves rejection. This audit is a separate CPU artifact and is not yet bound into the eight exact construction bundles or canonical delivery acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py preflight` passed (`preflight-nov23.log`). `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229439__NRS-484B-450-1o__motor_vehicle_driver/tests -v` passed 14 tests (`cpu-tests.log`). Next bind the independent media audit to the exact saved attempts and implement the Native camera writer, then rerun offline and compatibility proofs after updating every construction bundle. The package remains partial.

Assignment-scoped static gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C229439__NRS-484B-450-1o__motor_vehicle_driver --complete` exited 0 (`checkpoint-check.log`). Exact strict gate with `--require-delivery-ready` exited 1 at `Preparation acceptance failed: partial/missing packages remain` (`strict-check.log`); `result.json` stays partial.

## 2026-11-24 eight-case full-media finalizer checkpoint

`finalizer.py` now runs the independent `saved_media_audit.audit_media` after the original row/source check and before writing an observation result. It requires 900 contiguous 20 Hz Native frames and decodes all 3,600 source-hashed PNG images across the four camera archives. The production CLI uses the declared 1920x1080 front and 1280x720 rear/left/right profiles. The focused test uses a 2x2 diagnostic profile override, checks a successful full decode and proves a changed pixel binding prevents result creation. This is a software integrity proof; sign legibility and physical scene success remain unverified.

`refresh_inline_bundles.py` updated the eight exact constructions with the new finalizer and media-audit source snapshots. Every construction hash and every refreshed offline log is bound in `execution-manifest.json`; all eight `runtime.py offline` materializations exited 0. `tests/test_bundles.py` checks exact IDs, embedded source bytes, manifest hashes and log receipts. The focused suite passes 15 tests in `cpu-tests.log`; pinned preflight and scoped static exit 0. The exact scoped strict check exits 1 on truthful partial status, with log hashes in `result.json`.

Remaining CPU work: concrete Native CARLA adapter and camera writer, semantic proposals, case-specific positive/negative compatibility and saved-only process receipts, and canonical delivery/comparison bindings. Original map/device authority, physical sign visibility and actual captures still require local review.
