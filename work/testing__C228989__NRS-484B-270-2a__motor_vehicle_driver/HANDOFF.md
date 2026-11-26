# testing__C228989__NRS-484B-270-2a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.270(2)(a) — When overtaking or passing a bicycle, an electric bicycle or an electric scooter proceeding in the same direction, the driver of a motor vehicle shall exercise due care and: If there is more than one lane for traffic proceeding in the same direction, move the vehicle to the lane to the immediate left, if the lane is available and moving into the lane is reasonably safe.
Assigned branch(es): Due care; lane-movement branch conditional on constructed lane geometry and circumstances.
Cell: C228989 (road, overtake, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C228989__NRS-484B-270-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 qualifying pass and lane-source checkpoint

The exact NRS 484B.270(2)(a) applies to a motor-vehicle driver overtaking or passing a bicycle, electric bicycle or electric scooter proceeding in the same direction. Due care remains applicable; the immediate-left lane movement clause depends on more than one same-direction lane, availability and reasonable safety. `case-plan.json` now holds fourteen exact targets: three qualifying control types crossed with open/occupied left-lane traffic and move/stay requests, plus one-lane bicycle pass/follow controls. Eight comparisons isolate the intended lane move, requested traffic context, control kind and one-lane due-care contrast. No accepted recording is listed. Availability, reasonable safety and due care have no invented legal cutoff.

`pass_measurements.py` reopens hash-sealed original context and 20 Hz actor trace, rejects diagnostics, requires motor-vehicle driver and qualifying control rider identities, source-backed lane headings/adjacency/restrictions/traffic/obstruction histories, and eight world-space body vertices for both actors. It verifies the control starts entirely ahead of ego in the same lane, records the first sampled full-body pass, ego lane and left-lane occupant inventory at that frame, and leaves all legal judgments unresolved. The CLI writes replayable JSON only after successful source checks.

Nine focused CPU tests passed in `cpu-pass-tests.log` including CLI replay, wrong lane direction/adjacency, wrong control kind, control not ahead, missing traffic inventory, wrong original initial lane, changed bytes and diagnostic receipt rejection. Static scoped check passed in `assignment-check.log`. Exact scoped strict check failed on truthful partial status in `strict-gate.log`. Current proof hashes are in `result.json`. Next CPU work: bind a reviewed real Native lane packet and build fourteen exact scenes/controllers, synchronized camera capture and full saved media audit, finalizers/proposals, exact offline and positive-negative compatibility and saved-only delivery/comparison audits. Physical lane availability, actual safety, due care and camera visibility require later review.

## 2026-11-23 per-frame physical control checkpoint

`pass_controller.py` now turns each of the fourteen planned exact cases into adapter-neutral one-frame control intent. It binds the law, cell, motor-vehicle actor, qualifying control kind, requested lane count, requested traffic occupancy and maneuver. A sampled occupied, restricted or obstructed left lane inhibits a requested move and holds ego back. Open-lane move, deliberate stay, one-lane pass and one-lane follow are distinct commands. Lane identity, initial same-lane position, positive longitudinal gap and finite relative motion are required; missing or conflicting source state fails closed. These are physical scene control requests, not legal determinations of availability, reasonable safety or due care.

Pinned preflight passed in `cpu-preflight.log`. Fifteen focused tests passed in `cpu-pass-tests.log`, including all fourteen plan rows and adverse occupancy/control conditions. Scoped static check passed in `assignment-check.log`. Exact scoped strict check exited 1 on truthful partial status in `strict-gate.log`. Hashes are recorded in `result.json`; `pass_controller.py` SHA256 is `3672dfab1158cba6f7cae3789f0bfc6f3d98d487fcf87c6b8e0356250aaaee37` and its focused test SHA256 is `f8c19d3e11d8a2d49de866932914eff4e72543226ddf41f2cbe05e6973fb28e9`.

Remaining CPU work: bind reviewed Native map/lane and vehicle/control blueprints to the source packet, implement CARLA adapter/actor spawning and frame-by-frame controller invocation, capture synchronized four-camera 20 Hz original media and trace, then implement case finalizers and semantic proposals with positive/negative compatibility, saved-only delivery and all eight comparison audits. The physical captures and legal judgments remain unverified.
## 2026-11-26 full-frame lane-transition repair

The prior controller required ego and the qualifying control to remain in the same lane and the signed longitudinal gap to remain positive at every frame. That made the requested immediate-left movement and a completed pass fail partway through the 900-frame capture. `pass_controller.py` now checks the starting same-lane/ahead condition and planned open/occupied traffic on the initial observation, accepts the surveyed immediate-left lane and signed gap on subsequent observations, and continues to inhibit a new move when later occupancy, restriction or obstruction is sampled. `pass_native_capture.py` marks only frame zero as initial. This is a physical control policy, not a legal safety finding.

`SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c228989-owner-nov26 TMPDIR=$PWD/.runtime-work/c228989-owner-nov26 PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C228989__NRS-484B-270-2a__motor_vehicle_driver/tests -v` passed 24 tests, including a full 900-frame original-shaped synthetic capture through the lane transition and completed pass. The test mocks encoding and cannot establish real pixels. `.venv-cpu/bin/python runtime.py preflight` passed with the installed CPU stack, FFmpeg and Lean. `.venv-cpu/bin/python worker_check.py --assignment testing__C228989__NRS-484B-270-2a__motor_vehicle_driver --complete` passed static checks. Logs and hashes are recorded in `result.json`. Status remains partial: selected constructions and saved finalizer integration, exact offline/compatibility/saved proofs, physical and independent delivery/comparison audits are still CPU work; original lane availability, reasonable safety and due care stay unresolved for local review.

`pass_capture_audit.py` now independently reopens the original source receipt, context, trace and camera frame map; checks exact case, 900 joined 20 Hz frames, four camera file hashes and full FFprobe/FFmpeg decoding; and rejects altered source bytes. The full-frame fixture test calls the auditor with a mocked decoder (four invocations) and verifies changed-trace rejection. This proof covers software integrity and decode invocation only: synthetic fixture bytes do not prove video visibility or physical completion. The capture audit is separate from the still-missing canonical delivery audit and selected bundle proofs.
