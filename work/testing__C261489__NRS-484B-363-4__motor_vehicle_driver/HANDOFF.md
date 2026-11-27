# C261489 — NRS 484B.363(4) school-zone passing

Status: partial. The exact scoped static partial check passes. The strict delivery-ready check has not passed, and `result.json` remains partial. No original CARLA recording or physical/legal acceptance is claimed.

## Completed preparation

- Read the frozen exact law and device definition. The plan covers same-direction pass/zone activation, school session, both 30-minute boundaries below/at/above, class hours and nonflashing operational beacon, inactive sign without operational beacon, no pass and outside-zone controls. `case-plan.json` contains 12 exact cases and 9 controlled comparisons. Equality at a 30-minute boundary is measured and left for legal review.
- Each case has a source-gated inline primary construction, 20 Hz/900-frame/four-camera profile, independent timing and vehicle-pass source joins, a requirement measurement contract, and case-specific diagnostic source recipe. The sources are diagnostic; no school calendar, surveyed zone or actual beacon observation is inferred from them.
- Fresh offline proofs pass for all 12 cases after the beacon timing validation change. Fresh positive/negative compatibility proofs pass for all 12, including selected analysis, Lean decoder, full media decode and missing-source rejection. `run_offline.py` and `run_compatibility.py` reproduce them with scratch under `.runtime-work/c261489-owner-nov27b/`.
- Canonical semantic proposals validate against the pinned runtime (13 stages, 12 selected cases). Diagnostic delivery acceptance positive/negative tests pass for all 12 with independent four-video decoding and source hash checks. The controlled comparison auditor has a positive and fixed-route rejection test. Focused CPU suite: 19 passing tests in `cpu-focused-tests.log`.
- Native capture and output bridge code uses pinned same-tick `PipelineCapture`, source-sealed trace and four cameras. An external, source-hashed reviewed site and operator are still required for real CARLA execution. The fake-world 900-frame capture and world-restoration test passes.

## Remaining worker-owned CPU work

1. Complete a reviewed Native operator with actual actor, lane-change, beacon, camera and map acquisition; bind it without changing frozen inputs/runtime. Retain source hashes and source-gated site packet.
2. Add one engineering fallback for the declared physical lane-change/coverage risk to each linked case. Run its exact offline and positive/negative compatibility proofs, preserving all case/comparison variables.
3. Run and bind recorded-only `process-saved` fixture proofs for all cases. Compatibility attempts cannot be reused directly after manifest edits because their candidate-selection receipt binds the previous manifest hash; materialize fresh case-specific fixtures in `.runtime-work/` for each run.
4. Bind the 9 comparison audit commands and test positive/negative case-specific differences. Provide this assignment's queue proposal to the lead for integration into shared files. Finish independent branch/candidate review.
5. Rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C261489__NRS-484B-363-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failure before changing `result.json` to ready.

The actual GPU checks after CPU readiness are the physical pass, zone geometry, beacon lamp indication in pixels, camera coverage and original recording review. All temporary files stay under `.runtime-work/c261489-owner-nov27b/`.
