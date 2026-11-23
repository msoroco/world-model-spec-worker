# testing__C109749__NRS-484B-253__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.253 — The driver of a vehicle within an intersection intending to turn to the left shall yield the right-of-way to any vehicle approaching from the opposite direction which is within the intersection or so close thereto as to constitute an immediate hazard, but such driver, having so yielded and having given a signal when and as required, may make such left turn and the drivers of all other vehicles approaching the intersection from the opposite direction shall yield the right-of-way to the vehicle making the left turn.
Assigned branch(es): Initial yield duty; opposing vehicle within intersection..
Cell: C109749 (intersection, left_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 6. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 8. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 8 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 exact-case and CPU construction checkpoint

The original NRS 484B.253 text has four relevant clauses in this cell: initial yield when an opposite-direction vehicle occupies the intersection; the alternative immediate-hazard approach; permission after yielding plus signal when required; and the later reciprocal duty. The frozen branch witness singles out the first clause, but the full law demands all four. `case-plan.json` now names eight exact targets: `inside_yield`, `inside_no_yield`, `approaching_yield`, `approaching_no_yield`, `signal_given`, `signal_omitted`, `reciprocal_yield`, and `reciprocal_no_yield` (each prefixed by the assignment ID). Five controlled comparisons isolate initial yielding, approach location, signal, and later opponent response. Six frozen accepted case IDs were retained as historical metadata identities, without claiming that metadata proves these physical facts. The two additional signal and reciprocal reference cases are planned, not accepted recordings.

`left_turn_measurements.py` requires original source identity, a 64-character map hash, eight world-space body vertices per vehicle, frame-ordered speed/control histories and a reviewed intersection polygon. It preserves separate any-vertex, center and full-body occupancy, opposite-heading cosine, signal, braking, commitment and clearance. It rejects absent provenance and missing fields. The comparison routine rejects map changes, duplicate source identity, unequal frame windows and absent declared measured differences. It does not decide whether an approach is an immediate hazard or whether right-of-way was legally yielded. `left_turn_controller.py` requests distinct wait/turn, signal and later-opponent policies from actual Native tick flags. Its requests are not observed outcomes; downstream path tracking and original controls still need construction.

The eleven assignment tests passed in `cpu-left-turn-tests.log` (SHA256 in `result.json`), exercising inside/outside body occupancy, opposite approach heading, source rejection, comparison differences and the controller branches. `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete` passed in `assignment-check.log`. The exact strict command still fails at preparation acceptance because status remains partial; see `strict-gate.log`. CPU preflight passed with the updated pinned environment.

Next worker-owned CPU work: bind a real source-hashed Native intersection map, route and original occupancy source; construct and test all eight exact CARLA scenes and camera policies, finalizers, semantic proposals, per-case offline/compatibility positive and negative receipts, saved-only processing, and independent delivery/comparison audits. Review the eight source-hashed judgment range targets in `judgment-probe-plan.json`; two strict count endpoints are impossible in their observable domain and must remain explicit. Actual CARLA motion, delivered pixels and source-bound legal coverage remain unverified until later acceptance.

`native_intersection.py` adds an original-map packet validator: it requires a source-hashed junction, physical boundary polygon, connected approach/intersection/exit waypoints, a left-turn route, opposite-direction opponent route and vehicle blueprints. Four fake-map CPU tests reject right turns, same-direction traffic and wrong junction provenance. The refreshed suite has 15 passing tests in `cpu-left-turn-tests.log`; the current hash is in `result.json`. This validates packet structure only; no real Native map was bound or run.

## 2026-11-24 sealed saved-trace checkpoint

`saved_left_turn.py` now binds the exact case ID to an acquisition receipt and the unmodified byte hashes of the original map packet and 20 Hz trace. It verifies map identity, contiguous frames and timestamps before calling the existing body-occupancy and heading measurements. The output preserves all three source hashes and explicitly leaves physical acceptance and legal judgment unresolved. The receipt is a prospective Native acquisition contract; no original CARLA source was supplied here. The fake fixture exercises the saved-only path without claiming a real recording.

The 21 tests in `cpu-left-turn-tests.log` include positive source joining and rejection of diagnostic fixtures, changed bytes, wrong case ID, dropped frames and false cadence. The exact static assignment command passed in `assignment-check.log`; the strict command failed on truthful partial status in `strict-gate.log`. Passing log hashes are declared in `result.json`. Next CPU work is a Native acquisition writer that produces the specified receipt from actual world/body/control snapshots, followed by exact-case finalizers and all eight delivery bundles, proposals, compatibility receipts, saved processing and independent audits. The six historical accepted entries still have metadata only, so source-backed reuse cannot yet be established.
