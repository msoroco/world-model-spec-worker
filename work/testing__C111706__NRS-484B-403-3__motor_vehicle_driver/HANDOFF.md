# testing__C111706__NRS-484B-403-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.403(3) — The driver of a vehicle shall not make a U-turn in a business district, except at an intersection or on a divided highway where an appropriate opening or crossing place exists.
Assigned branch(es): Intersection exception with surrounding vehicle context..
Cell: C111706 (intersection, u_turn, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111706__NRS-484B-403-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

Authored three exact cases in `case-plan.json`: `__intersection_vehicle_near`, `__approach_before_intersection`, and `__intersection_vehicle_far`. The `intersection_exception_location` comparison changes the ego U-turn location relative to the reviewed statutory intersection boundary while retaining the same other-vehicle route and timing. The `surrounding_vehicle_context` comparison changes only the other-vehicle arrival timing. The assigned cell remains intersection/U-turn/other-vehicle; the approach case uses the same intersection map but turns before its boundary. No original source yet proves that an actual map realizes either route. The law also permits a divided-highway opening or crossing-place exception; that layout is incompatible with this fixed intersection cell and needs separate compatible-cell binding by the lead if in batch scope. Business-district classification remains an explicit reading assumption pending original source review.

`construct.py` now hash-checks a reviewed site packet, binds case identity and the map/district/boundary sources, checks opposite-lane route continuity and junction occupancy, and lazily calls `try_spawn_actor` for distinct ego/other motor vehicles. It destroys the first owned actor if the second spawn fails. No live CARLA connection was attempted. `native_uturn.py` checks a sealed original-frame projection for frame/time continuity, ego/other identities, map lane continuity, heading reversal, junction observation and other-vehicle center distance. Its CLI writes only computed measurements and leaves district classification unresolved. The Native audit also requires a source-bound intersection polygon and recorded ego body corners and reports frames with the entire sampled footprint inside. These original sources remain absent in this worker package, and sampled containment does not establish the legal boundary or continuous swept occupancy.

CPU proofs: 13 tests pass in `cpu-tests.log`; `.venv-cpu/bin/python worker_check.py --assignment testing__C111706__NRS-484B-403-3__motor_vehicle_driver --complete` exits 0 in `assignment-check.log`; the same command with `--require-delivery-ready` exits 1 in `assignment-strict.log` with `Preparation acceptance failed: partial/missing packages remain`. All three log hashes are in `result.json`. The strict failure is truthful status, not an external dependency claim.

Next CPU work: obtain/source-bind an actual suitable map/intersection/district site and per-case route transforms; implement a non-teleporting U-turn controller and 20 Hz capture with original footprint and intersection geometry; author exact bundles, semantic proposals, measurement contracts, source-bound diagnostic recipes, positive/negative compatibility and saved-only execution receipts, independent delivery and comparison audits, justified fallbacks and manifest; rerun the exact strict gate. GPU work is later physical realization and video/trace review only.

## 2026-11-24 original Native acquisition checkpoint

`capture_uturn.py` now records 900 consecutive original world ticks at synchronous 20 Hz for the exact case. It retains the source-sealed site/map/route/district/boundary bindings; original ego and other actor IDs, waypoint road/lane/junction, pose and body vertices; and source-frame/time continuity. The caller supplies both control callbacks and a full-brake callback, allowing a reviewed non-teleporting route controller to be connected without importing CARLA during CPU tests. It writes atomically only after the complete trace; a readback or timing failure brakes both actors and leaves no published trace. Cameras, world settings restoration and actor destruction remain caller-owned. The current CPU fake validates the interface and negative cases; it is not a physical U-turn or a legal determination.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C111706__NRS-484B-403-3__motor_vehicle_driver/tests -v` passed 17 focused tests in `cpu-tests.log`. The assignment-scoped `worker_check.py --complete` passed in `assignment-check.log`; the exact scoped strict gate exited 1 in `assignment-strict.log` because this package is still partial. Their SHA256 hashes are in `result.json`.

Next CPU work: source-bind a reviewed live intersection/business-district site and per-case route transforms; implement and test the actual waypoint/controller path, synchronized four-camera acquisition, per-case semantic bundles and measurement contracts, source-specific diagnostics and positive/negative compatibility, saved-only processing and independent delivery/comparison audits. Keep statutory district and intersection classifications unresolved pending original source review.
