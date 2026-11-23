# testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver

Status: partial executable CPU construction. Seven exact proposed cases and three controlled comparisons are in `case-plan.json`; none is a verified recording.

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
