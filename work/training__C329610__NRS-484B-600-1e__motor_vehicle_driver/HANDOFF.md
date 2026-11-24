# NRS-484B-600-1e at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Witness branch: Accepted membership requires exact source review.

Comparison variable: `vehicle_speed_mph`. Proposed physical probes: drive below 80 mph; drive above 80 mph. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C329610__NRS-484B-600-1e__motor_vehicle_driver/assignment.json`, SHA-256 `6cbbe25b45ec31380cbf79470351344a91c2306c2970c2affdd5449fd7284105`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: 03447c598de1182f0a74d36cf80cb2f21f5afa727457978bee3b86255c6cfcaa, 2470b339011cd73ce1e604bfcd82d1a02a1977ddcecf6251d3f11f348d50cb3c, abe44714660b12c1daa34b44eb9fc8e8466096678dea8c7513631026c662f47a. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Accepted recording IDs are membership context only and lack an equivalence receipt. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact left-turn speed construction checkpoint

The supplied statutory speed cap is 80 mph “in any event.” The authored 75 and 85 mph requests are engineering contrasts, not observed Native speed or legal labels. Three accepted recording IDs remain membership context without a local source-hashed equivalence review for this exact requirement; no reuse is claimed. `case-plan.json` now maps each source observation term to original velocity, frame and vehicle identity sources.

`native/road.xodr` derives the C329610 same-cell two-way left-turn scene from the NRS 484B.413(2) package. The approach is extended to 423 m without moving its endpoint; the intersecting roads, junction and left-turn arc remain byte-equivalent in parsed XML. `native/audit_requests.py` checks that provenance. Two separate inline exact constructions under `draft-native/` request 600 frames at 20 Hz for 30 seconds, four named source cameras, the same role and same road sequence 1 → 13 → 4. Probe A requests 75 mph and probe B 85 mph during the initial approach, then both decelerate to request the left turn. `native/speed_turn.py` computes mph from the vector magnitude, checks complete frame/time and road joins, rejects discontinuous requests, and records the diagnostic count above the exact 80 mph cap without claiming original motion. The independent comparison audit confirms both authored routes include the turn and differ in requested speed profile.

Both exact constructions passed pinned `runtime.py offline` CPU checks with commands and hashed logs in `draft-native-manifest.json`. The ordinary assignment-scoped `worker_check.py --complete` checkpoint passes. This package remains `partial` with unselected drafts. Remaining worker-owned CPU work includes Native vehicle controller/capture with original velocity and four source-camera seals, exact selected-case positive/negative compatibility, actual process-saved, physical-risk fallback proofs, and independent delivery/comparison audits. The 85 mph request may not be physically realized by the local vehicle; local execution must measure it, not infer it from the command.
