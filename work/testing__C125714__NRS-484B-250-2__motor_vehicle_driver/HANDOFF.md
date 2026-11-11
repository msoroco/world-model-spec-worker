# NRS 484B.250(2), C125714: partial CPU implementation checkpoint

The assigned cell has a median opening, travel maneuver and another vehicle. The exact law addresses two vehicles entering an intersection from different highways at approximately the same time, with the vehicle on the left yielding to the one on the right. It excludes officially controlled intersections, subject to subsection 4, and opposite-direction approaches when one driver intends or makes a left turn. “Approximately” has no numeric legal window in the supplied text.

`case-plan.json` reviews all eight accepted metadata records: precedence, advance, other_later, opposite_straight, opposite_intends_left, opposite_makes_left, wide_same_crossing and wide_separate_crossing. Their frozen metadata establishes identity, accepted status, frame counts and decoder reports. The retained traces, videos, map/device sources and physical comparisons are not in this standalone export. No accepted original is queued for replay and no source-backed equivalence is claimed.

`entry_measurements.py` is CPU implementation work for retained raw sources. It joins `crossing_history.jsonl` to the original frame map, tests complete body intersection against a sourced polygon, records first entry frames and time delta, and retains highway IDs, approach headings and device-inventory provenance. It does not decide approximate simultaneity, left/right legal priority or any exception. Three tests pass in `cpu-tests.log`, including rejection of a missing device source and a stale frame join.

## Next CPU work

1. Verify the eight accepted originals against measured entry, map, direction, device and intention sources when retained files are available. Determine exact coverage and gaps without replaying them. Independently check the source definition governing separate roadway intersections; do not infer it from `wide_*` case names.
2. Build one genuinely uncovered selected case through the complete saved-processing path first: construct the crossing through the median opening and both approach routes, implement actor controllers and four named cameras, capture original body and device state, and finalize from retained raw sources. Run exact offline, positive/negative compatibility and `runtime.py process-saved` checks.
3. Complete all remaining controlled comparisons, three distinct physical-risk fallbacks for every selected case, semantic proposals, independent delivery/comparison audits, branch matrix and final review. Rebind current hashes after changes.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready`, then the full batch strict gate.

`.venv-cpu/bin/python runtime.py preflight` passes in the current environment. This package remains partial because construction and proofs are unfinished CPU work. Actual physical entry, visibility and any legal judgment remain unverified.

Current batch strict gate: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1; `strict-gate.log` records `ValueError: Missing result: testing__C125751__NRS-484B-250-2__motor_vehicle_driver`. That is the next missing package in batch order. It does not imply the three existing partial packages are ready.
