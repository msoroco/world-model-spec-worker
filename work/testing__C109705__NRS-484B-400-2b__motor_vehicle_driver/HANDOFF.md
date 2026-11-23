# testing__C109705__NRS-484B-400-2b__motor_vehicle_driver

Status: partial exact case plan with source-bound geometry, pair audit and lazy route policy. Four existing-recording case identities are mapped; no new recording is selected.

Exact law: NRS 484B.400(2)(b) — If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: After entering the intersection, the left turn must be made so as to leave the intersection to the right of the centerline of the highway being entered.
Assigned branch(es): Two-directional intersection within the general intersection layout..
Cell: C109705 (intersection, left_turn, centerline); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 4. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. The four exact prior-setting cases and two controlled comparisons are mapped. Bind them to original trace/map/video sources when available; no judgment-range entry applies to this law/actor.
3. Complete the source-survey route policy with actual Native spawn/capture and CPU test; author case-specific finalization, semantic proposals, diagnostic recipes, saved-only processing, delivery receipts and risk-based fallback assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## Exact departure construction checkpoint (2026-11-23)

The four exact prior setting IDs now appear in `case-plan.json.cases`: `near_centerline`, `farther_from_centerline`, `imaginary_near_centerline`, and `imaginary_farther_from_centerline`. They map to the four frozen accepted recording IDs, with two controlled comparisons: `departure_lateral_position` and `imaginary_departure_lateral_position`. Each pair fixes the connected two-directional left-turn approach, 45-second four-camera contract and its own centerline convention, varying only the requested departure lateral position. These are source-review and construction targets; original trace and video are absent from this export, so no new recording is selected or existing recording claimed sufficient.

`departure_geometry.py` is an executable saved-source measurement: it verifies case/road connection, driver control, two-directional highway context, source-identified mapped or imaginary destination centerline, original intersection-entry ordering and full-body departure corners. It projects every corner onto the destination direction's right normal, retains per-frame and overall extrema, and leaves statutory position judgment null. `comparison_audit.py` independently checks source hashes, case IDs, common map source, distinct trace sources, connected roads, centerline convention and observed ordering. It rejects a legal label; shared map and ordering alone do not establish identical approach motion or legal compliance. Both scripts have CLIs for eventual original source packets.

`cpu-departure-tests.log` (SHA256 `7a5b91ebcc24da168f250051d20a70d871e24252bb3b7f3eb5d283186713e8b3`) records 13 passing CPU tests for right-side projection under both directions, missing context/body/road, source tampering, invalid comparison context, unrealized difference and leaked legal labels; plus map opposition, connection, imaginary-line source, source map hash, pair isolation and bounded route control. Run with `.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v`. Pinned `.venv-cpu/bin/python runtime.py preflight` passed on this host.

Next CPU work: make an exact lazy CARLA/Native construction and original-map readback for all four cases, bind finalization to the exported original source packets, author canonical semantic proposals and four case diagnostic recipes, run exact offline and positive/negative compatibility, saved-only and independent delivery proofs, and bind the per-pair comparison audit. The original accepted metadata is insufficient to claim either comparison physically established; preserve its uncertainty and do not set `ready` until the assignment's exact strict gate passes.

`construction.py` now defines the four exact departure targets from an original source-hashed Native map survey. It checks two opposed permitted lanes on each sourced non-alley highway, connected approach/destination road IDs, marked or derived imaginary destination centerline, waypoint route, vehicle blueprint and camera plan. The pair shares its approach and controller policy; engineering lateral targets are 1.7 m and 2.7 m, never statutory cutoffs. Its bounded waypoint controller can be exercised on CPU. This is a route policy awaiting a surveyed map and Native actor/camera/capture implementation, not a claimed physical construction.
