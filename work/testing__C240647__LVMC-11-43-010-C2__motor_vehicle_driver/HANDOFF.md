# testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.43.010(C)(2) — The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle who intends to exit a roundabout: Shall use the right lane to turn right.
Assigned branch(es): Intended right-turn exit..
Cell: C240647 (roundabout, right_turn, lane_allocation); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 right-lane roundabout checkpoint

`case-plan.json` now has nine exact unexecuted cases and eight comparisons. It separates independent right-exit intent from actual right/through/no exit, right versus left circulating lane, lane changes before exit, through-intent controls and a single-right-lane geometry control. The fixed lane-allocation context and connected right-turn exit remain construction requirements.

`roundabout_measurements.py` accepts only a hash-sealed original Native context and 20 Hz trace. It requires source references for jurisdiction, roundabout graph, right lane and right-turn exit connector, operator/vehicle identity, independent intention and route. It verifies circulating lane membership and exit connector provenance, then preserves intended connector, last circulating lane and first observed exit connector separately. It does not infer intention from movement or resolve legal right-lane use from a single sampled frame. Diagnostic fixtures are rejected as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Seven focused tests passed (`cpu-roundabout-tests.log`, SHA256 `7151536e93573c74fafa86b341cdc7a1378843f8edb4bc8b24dfc11cd3506577`). Scoped static check passed (`assignment-check.log`, SHA256 `67b1861aeaa71da192d0d1b7a6cf87d42bc64ef758025d17ce10a03ca19aedc1`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `d44a2c257434165ed543c420c3379f422e7ad439873a05972b6bc6056f892222`, measurement `1515c982e999d6d6635dba5396a34e5c701911f6da0f33aadb3ac4c6e219c6f4`, focused tests `8f6c735f5ceacf65d9adb69cf5d9c48cbf7fb3c25172abf2b344ed11ea3979e4`.

Remaining CPU work: bind reviewed Native roundabout lane graph/jurisdiction and independent driver-intent records, construct nine physical scenes/controllers and synchronized four-camera original capture, verify full lane use through the connected right-turn exit, then implement finalizers/proposals, exact offline and positive/negative compatibility, saved-only delivery and eight comparison audits. Physical and legal acceptance remain unverified.

## 2026-11-26 selected delivery preparation

The previous checkpoint above is superseded. Nine selected original-source-gated Native cases and eight fixed-condition comparisons now have current-hash CPU proof. The final fanout passed 18/18 offline and compatibility primary/fallback paths, 9/9 saved-only analyses, 9/9 physical-preparation and lifecycle probes, 9/9 four-view delivery decode and negative-source audits, and 8/8 comparison audits. Twelve unit tests and pinned preflight passed. The exact scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver --complete --require-delivery-ready` exited 0; log `cpu-strict-gate.log`.

The original roundabout map, independent operator intent, circulating lane readback, actual exit connector and four synchronized camera pixels are explicit source acquisition gates. Diagnostic CPU fixtures establish package compatibility only. Live CARLA motion, original capture quality and legal judgment remain for the GPU delivery step. The shared GPU queue remains for lead integration.

Stable SHA256: `case-plan.json` e3c5467e7520a51699c427c94b3ffcd3d4757e7dc758c1662e02f6b46e209129, `execution-manifest.json` ede49e972958980f2d9a5a074d7bab23a453ab3af5d3d36d358530f6a4ddd878, `gpu-queue-proposal.json` 25fe0b203b20fa4a22c71ebdbf009b0da7f2195736d9ce16b6633f71ae8deb27, `result.json` d91200dc67d573d205e395a38092d840650651b050aca96b8f68b9029c7717a8, `cpu-strict-gate.log` 67b1861aeaa71da192d0d1b7a6cf87d42bc64ef758025d17ce10a03ca19aedc1.
