# NRS-484B-627-1b at C132924

## 2026-11-26 current-runtime continuation

Status remains **partial**. Independent reading of the frozen law found an exception to the extreme-right-lane duty when necessary to pass another slowly moving vehicle. `case-plan.json` now retains the right/left impeding pair and adds `necessary_pass` versus `post_pass_linger` to test pass duration and return right after observed clearance. Four selected-required dispositions separate impeding, marked lane topology, pass necessity and post-pass lane occupancy. These are physical targets; they do not decide whether traffic is legally impeded or passing is necessary.

`native/controller.py` uses observed ego/follower/slower-vehicle state to request right-lane, left-lane, pass and post-clearance phases. `native/capture.py` requires an original per-case operator survey through `SCENARIO_CONTEXT_SURVEY`, reads back Native map lanes and actor positions, controls ego/follower/slower vehicle, captures 600 source frames and four synchronized cameras, seals acquisition and restores the world. `native/measure.py` joins source frames to camera frames, derives body-lane occupancy, follower speed/position and pass/clearance intervals, and leaves legal judgments null. This code has not run in CARLA. Original marked-lane topology, actual physical motion, pixels and pass necessity remain unverified.

`native/build_config.py` generated the canonical first-case four-camera 30-second config. `native/runner.py --check` passed four controller branches; four focused controller/measurement tests passed, including missing follower and broken Native/video join negatives. Test log SHA-256 `695740ed3e331ab197d319c0583c80d3da82c6f6907858707263c696687d7446`. Current runtime verify/preflight and assignment-scoped partial check passed. Next CPU work is to create all four exact inline constructions and measurement contracts, verify original-survey handling with CPU fakes, run current-runtime offline/public compatibility/saved-only positive and missing-source negatives, author canonical semantic proposals and physical/lifecycle/delivery/comparison audits, then run the exact strict gate. No package is marked ready.

## Current CPU construction checkpoint

`native/measure_roundabout.py` now reads hashed retained geometry and actor rows and measures right/left roundabout lane occupancy, immediately trailing traffic, and source speed ordering. `prove-roundabout-lanes.py` created two 600-frame, 20 Hz synthetic diagnostic traces: extreme-right and inner-left radial lanes. Both hold the same 3 m/s ego speed, 5 m/s follower speed, and 0.1-radian trailing offset. Each has 600 follower-behind and ego-slower frames; lane occupancy is 600 extreme-right versus 600 inner-left frames. The proof rejects altered source bytes, absent follower rows, and Native frame/time gaps for each trace (six negative tests). Proof SHA-256: `54d8dad4870e2cbd507bcfa573e96f36dab605fffb3b07b86adeec85ee0a9180`.

`audit-roundabout-lanes.py` independently checks the frozen statutory text, retained source hashes and raw rows, roundabout lane geometry, controlled radial difference, speed and timing policy, and the limited claims. It passed; audit SHA-256 `8e25c66443ad622e680e92284b0e174ed333e216c6fde5282a3efffb976ff6b0`. These are synthetic CPU geometry diagnostics, not Native motion, selected delivery, accepted evidence, or a legal conclusion. Speed ordering and trailing position alone do not settle whether traffic is impeded; necessity and duration of a pass remain unproved.

Verification commands: `.venv-cpu/bin/python work/training__C132924__NRS-484B-627-1b__motor_vehicle_driver/prove-roundabout-lanes.py` and `.venv-cpu/bin/python work/training__C132924__NRS-484B-627-1b__motor_vehicle_driver/audit-roundabout-lanes.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `7d2e4ba8abe19730abb899cd502d9fb749dec8368576db7e9dbb94ae60153ad0`. `.venv-cpu/bin/python worker_check.py --assignment training__C132924__NRS-484B-627-1b__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `2ba78d4b736230ac183773aee1fd422826b10a46424eb7542d9555bc9456069a`. This check validates a partial checkpoint only.

Remaining worker-owned CPU work: implement exact Native roundabout routes/controllers, physical two-lane and following-traffic construction, explicit pass-exception case and time interval, four distinct 30-second constructions per selected case, four-camera capture, source-bound saved processing and Core/Lean/final decode positives/negatives, statutory and accepted-evidence review, and independent delivery/comparison audits. Retain partial status until the assignment-scoped strict gate passes.

Actor: `motor_vehicle_driver`. Frozen cell: `multilane_roundabout` / `travel` / `other_vehicle`.

Witness branch: Extreme-right-hand-lane duty on a multilane roundabout route..

Comparison variable: `impeding_vehicle_lane_position`. Proposed physical probes: use extreme right lane while impeding following traffic; remain in left lane while impeding following traffic. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C132924__NRS-484B-627-1b__motor_vehicle_driver/assignment.json`, SHA-256 `117cff847b15473b076fcbcd375d2d00fd472abd5c0c68ec923e12ec27ced68c`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
