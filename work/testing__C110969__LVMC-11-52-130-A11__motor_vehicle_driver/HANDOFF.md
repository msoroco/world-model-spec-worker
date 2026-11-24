# testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver

Status: partial executable CPU construction. Seven exact proposed cases and three controlled comparisons are in `case-plan.json`; none is a verified recording.

## 2026-11-24 saved-source and loaded-map checkpoint

- `saved_delivery.py` independently joins a sealed exact-case measurement packet, 900 contiguous Native world frames, a 20 Hz frame map, and four named camera receipts. It verifies each referenced original PNG hash and rejects escaped paths, changed hashes, missing cameras and frame drift. The fixture path is explicitly diagnostic; the audit keeps full video decode, actual pixels, participant completeness, physical completion and legal necessity unresolved.
- `native_map.py` binds all seven exact case IDs to a loaded map's OpenDRIVE hash, map name, local intersection bounds, route, actor dimensions and provenance fields, and computes the requested local halt pose. A caller must still supply a genuinely reviewed packet and physical map/route evidence.
- `cpu-geometry-tests.log` records 29 passing focused tests, including positive and negative saved-source and loaded-map cases. The assignment static check passes; the exact strict gate returns exit 1 because this package remains partial.
- Next CPU work: integrate original pose, four-camera and exception-context acquisition into a single Native runner; author case-specific finalization, semantic proposals, exact offline and positive/negative compatibility bundles, process-saved receipts, delivery audit and execution manifest. The separate parking alternative still needs a compatible binding review. No diagnostic source establishes statutory coverage.

## 2026-11-24 Native source and comparison checkpoint

- `original_capture.py` now writes an original 900-tick synchronous 20 Hz Native ego pose and requested-control trace from a caller-owned world, actor and reviewed world-to-local mapping. It checks frame continuity, finite position and velocity, approach alignment through the existing controller, and intersection intrusion, and applies a final brake during cleanup. It does not own the four cameras, observed traffic/directions, world restoration or the sealed acquisition receipt; these still need a full runner.
- `measure_gap.py` now requires at least one contiguous 40-frame observed halt and reports its exact interval. Scattered stationary flags cannot satisfy the two-second dwell.
- `comparison_audit.py` reads seven exact saved measurements and source-hashed context packets. It rejects missing/duplicate cases, changed fixed map/vehicle/route/camera conditions, wrong numeric targets, changed activity/exception cause, diagnostic sources, missing observation files and hash/path tampering. It returns measured gaps and leaves legal necessity unresolved. This is an independent software audit; the test fixture does not establish physical evidence.
- `cpu-geometry-tests.log` records 23 passing tests with `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver/tests -v`. The exact static check passed; the exact strict check returned exit 1 because status remains partial.
- Next CPU work is to bind a reviewed intersection map/route and actor, acquire original traffic/police/device context with four cameras, integrate finalization and sealed acquisition, author semantic proposals and exact offline/compatibility/saved-only bundles, and add the delivery audit and full manifest. Source-hashed intended cause is not proof of actual conflict necessity or legal compliance.

Exact law: LVMC 11.52.130(A)(11) — No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: Within fifteen feet of an intersection.
Assigned branch(es): Intersection proximity during destination stopping or standing.
Cell: C110969 (intersection, stop_stand, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## 2026-11-23 construction checkpoint

- `case-plan.json` now proposes stop at 14, 15 and 16 ft from the source-bound intersection boundary; a standing contrast; and traffic-conflict, police-direction and device-direction exception contexts. The 15 ft threshold comes from the exact statute. The planned 14/16 ft offsets are engineering probes. No legal outcome or necessity is inferred from their names.
- `intersection_geometry.py` constructs a requested front-body pose and checks body-to-boundary gap across east, west, north and south approaches. `stop_controller.py` gives a longitudinal throttle/brake request using live pose and speed. These are map-independent portable components; neither writes a Native capture nor establishes realized motion.
- `measure_gap.py` requires a source-hashed original 900-frame 20 Hz pose trace, source-hashed map geometry with identity and provenance, actor binding and at least two observed halt seconds. It reports raw-source hashes and minimum/maximum halt gap, without a legal finding. Synthetic positive and rejection tests do not count as accepted capture.
- `cpu-geometry-tests.log` records 12 passing tests, including four approach directions, exact distance probes, different body lengths, command behavior, changed original-source rejection, missing map-provenance rejection and short-trace rejection. Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver/tests -v`.
- The exact strict command was rerun and returned exit 1 with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log`. Status remains `partial` because the listed CPU deliverables are unfinished.

## Next CPU actions

1. Bind a reviewed CARLA intersection map and exact boundary geometry to the local coordinate frame, actor blueprint, route and spawn; implement the CARLA runner and original source writer for all seven cases. Review whether the statutory parking alternative can be realized within the frozen stop_stand cell before claiming full branch coverage.
2. Implement case-specific finalization, semantic proposals, positive/negative compatibility and saved-only paths, and independent delivery and comparison audits. Test each exact case and any risk-justified fallback. Keep physical-risk assessments in each manifest entry.
3. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver --complete --require-delivery-ready` after the CPU package is complete; repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed in the refreshed CPU environment; the assignment static check passed; the assignment's 12 focused tests passed. These are CPU construction checks, not delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
