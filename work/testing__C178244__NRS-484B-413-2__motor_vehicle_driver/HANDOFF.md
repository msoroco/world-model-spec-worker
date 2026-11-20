# C178244 CPU handoff — NRS 484B.413(2)

Status: **partial**. The frozen assignment fixes a paved-road left turn with `other_vehicle`. Its branch label mentions a business-district right turn; this package covers only left-turn alternatives. C378304 remains responsible for the original right-turn branch. No accepted recording exists in the frozen evidence inventory.

## Current first selected case

`left_business_at_100_ft` now has an inline exact construction (`construction.json`, SHA-256 `3c9a57744e673d4a1652b81260f0e765870855695e2e68ed071e13ff5ea0b120`) with a connected left-turn OpenDRIVE route (`native-map-plan/left-turn-approach.xodr`, SHA-256 `133932810f75ac785039068a94ceab89e8d8aa2a1fa6adf83bdf200f2bd48ced`), a second Native vehicle on the departure lane, left-indicator command/readback, four named camera writers, frame/trace joins, original-source distance measurement and a recorded-only finalizer. The earlier `turn_signal_control.py` and `turn_signal_measurements.py` components and tests are retained. The new source-shaped diagnostic has two participants and original lamp-state attributes; its black videos and district assertion establish software compatibility only.

Current proofs for this exact construction:

- `runtime.py preflight`: passed with pinned Python CPU packages, ffmpeg/ffprobe and Lean/lake 4.28.0.
- `runtime.py offline --manifest work/testing__C178244__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C178244__NRS-484B-413-2__motor_vehicle_driver__left_business_at_100_ft --output .runtime-work/c178244-left-at-primary-offline-v2`: passed; `primary-offline.log`.
- `runtime.py compatibility` for that manifest/case at `.runtime-work/c178244-left-at-primary-compat-v3/analysis`: passed positive measurement, original-source validation, Core/Lean decoder, four-camera and final decode checks. Removal of `drive_history.jsonl` was rejected as required. Bound receipt/logs are `primary-compatibility.json`, `primary-analysis.log`, and `primary-negative.log`.
- `runtime.py process-saved` for the same case from that analysis to `.runtime-work/c178244-left-at-primary-saved-v3`: passed recorded-only processing and source preservation; `primary-saved-processing.json`.
- Seven local component/construction tests pass in `cpu-tests.log`; assignment-scoped `worker_check.py --complete` passes. Scoped `--require-delivery-ready` fails `Preparation acceptance failed: partial/missing packages remain`, because the batch is incomplete.

The first compatibility attempt with two participants failed `Mandatory observation coverage incomplete: ['sig.turn_indicator']`; the second actor lacked an original lamp-state observation. The diagnostic now supplies its explicit off state; the revised positive/negative compatibility and saved proofs above passed. Native capture still needs physical review of the actor placement, indicator pixels, actual path, and district frontage. A diagnostic site description is not verified legal district evidence.

## Next worker-owned CPU work

Construct and prove `left_business_under_100_ft`, `left_business_over_100_ft`, `left_other_under_300_ft`, `left_other_at_300_ft`, and `left_interrupted` with exact source recipes. Add three distinct physical-risk fallback constructions per selected case, with offline, positive/negative compatibility, and saved-only proof. Build source-backed business/other district and highway packets, canonical semantic proposals, source camera/duration plans, independent delivery and comparison audits, and queue bindings. Rerun every affected proof after construction or finalizer edits. Keep `result.json` partial until the assignment and full strict gates pass. Native CARLA motion and physical/legal acceptance are separate later checks.

The full strict gate attempted on this checkpoint with a 30-second cap exited 124 and left an empty `.runtime-work/strict-after-c178244.log`; it did not establish readiness. The most recent completed gate error supplied by the user is `Unapproved output: runtime/runs/scenario_pipeline/inputs/shared/manifest.json`. `runtime/` is frozen and was not edited. That generated runtime file also needs cleanup by the authorized launcher/environment process before a complete strict return can pass. This does not excuse the unfinished worker-owned cases above.
