# testing__C202480__NRS-484B-557__motor_vehicle_driver

Status: partial delivery preparation. No case is ready, no CARLA capture is claimed, and no legal verdict is assigned.

## Exact source and coverage

NRS 484B.557 requires an official stop sign governing a DOT-designated highway railroad grade crossing, complete cessation within 50 feet but not less than 15 feet from the nearest track, and due care before proceeding. Frozen accepted evidence inventory is empty. `case-plan.json` now lists nine exact cases: below/at/above 15 feet, below/at/above 50 feet, rolling passage, and clear/conflicted departures. Four comparisons isolate lower distance, upper distance, cessation, and departure conflict. Distance values are commanded body-gap targets; the statute does not specify a vehicle reference point, so measured original body-corner ranges remain unlabelled. No judgment-range entry exists for this exact law and actor.

## Implemented CPU construction and proof

`native_construction.py` requires source-hashed OpenDRIVE, crossing authority, rail geometry, official stop-sign landmark, and blueprint before requesting a Native spawn. It checks live map/sign identity and computes a stop centre from the reviewed rail and source half extent. Tests cover spawn, authority, tamper, map mismatch and sign absence. A reviewed real site packet and exact per-case runner bundles are still needed.

`native_control.py` requests approach, braking, stop hold, rolling and subsequent departure from live Native position/velocity, including both approach directions. One zero-speed frame is an engineering command state, not proof of cessation or due care.

`rail_stop_audit.py` verifies all five original source-file hashes, complete sequential 20 Hz frame timing, four body corners, nearest rail geometry, precontact zero speed, and subsequent movement. It preserves due-care review as unresolved. `comparison_audit.py` rejects absent original sources, changed fixed crossing context and missing or identical measured contrast. These are implementations and synthetic source-shaped tests, not captured evidence.

Focused command: `.venv-cpu/bin/python -m unittest discover -s work/testing__C202480__NRS-484B-557__motor_vehicle_driver/tests -v`. Result: 28 tests passed; `cpu-tests.log` SHA256 `a33a949f43b3667fc917baac000e7b9ba6d052fe2f479bf1a2fc6d57f38321f3`.

## Next CPU work

1. Author and independently review a real C202480 crossing site packet with source-hashed DOT or approved local designation, governing stop sign, nearest rail geometry, map and four camera poses. Do not infer authority from the visible sign alone.
2. Build nine exact runner/config/construction bundles, selected-requirement measurement contracts and canonical semantic proposals; bind each to the reviewed site. Add risk-based fallbacks only for concrete placement or visibility failures.
3. Run exact offline and positive/negative compatibility proof for every case and candidate. Implement saved-only processing, independent four-camera delivery audit and candidate-selection review; record all hashes in `execution-manifest.json`.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C202480__NRS-484B-557__motor_vehicle_driver --complete --require-delivery-ready`; keep status partial until it passes. After CPU delivery, actual motion, distance and camera visibility remain GPU checks.

No frozen input, runtime, or batch file was changed. No external blocker is asserted for remaining CPU work.
