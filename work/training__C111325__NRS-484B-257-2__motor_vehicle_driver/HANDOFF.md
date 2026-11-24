# training__C111325__NRS-484B-257-2__motor_vehicle_driver

Status: **partial**. No selected delivery cases, CARLA construction, CPU candidate proof, CARLA execution, or accepted recording is claimed.

Exact sources: `inputs/training__C111325__NRS-484B-257-2__motor_vehicle_driver/assignment.json` SHA-256 `0a3d4ae94a9035af420cd6e35ee8201a9339a4b8e03392ebbe9e049cb0c15dd7`; `witnesses.json` SHA-256 `45a508078f5ef2e29c9023084301b9733d6759b08a44f44faf9b35e12c6be87b`. The subsection 2 witness points to supplied NRS-484B-257-1 text for the incorporated stopping-location alternatives. Its physical application still needs source review.

The frozen cell is an intersection, travel, stop sign and motor-vehicle driver. Three unselected planning probes remain in `case-plan.json`. Accepted memberships are contextual only; none has a local source-hashed equivalence receipt.

## New CPU construction and proof

`stop_yield_saved_measure.py` is a saved-packet reducer for a signed non-through intersection and separately saved control inventory. It binds raw packet and inventory SHA-256, checks a contiguous 20 Hz / 30 s stream, computes first subject entry and exit, records pre-entry near-zero frames before the stated stop reference, identifies actual officer or signal control during crossing, and distinguishes a counterpart with no stop/yield obligation that is inside at entry or during crossing. It returns `legal_result: null`; its 0.1 m/s near-zero tolerance is a diagnostic engineering value only. It does not infer caution, immediate hazard or statutory compliance.

`prove_stop_yield.py` tests a 600-frame synthetic-native sample with subject entry at frame 200, exit at 260, near-zero pre-entry frames 160–179 and counterpart inside at entry through frame 239. Controlled negatives move the counterpart outside the crossing window, activate officer control, assign it a stop obligation, delete a frame, and make the subject sign ungoverned. Synthetic rows are in-memory and are not CARLA motion or saved camera pixels.

CPU proof: `TMPDIR=$PWD/.runtime-work/c111325-tmp .venv-cpu/bin/python work/training__C111325__NRS-484B-257-2__motor_vehicle_driver/prove_stop_yield.py` exited 0. `stop-yield-cpu.log` SHA-256 `8ee56eadf643b432d499822dc2f96de9b9bbef631c5aa7e64bdfa3e9af6b87bb`; reducer SHA-256 `4e1ed604ca081903f9e60ad96de419dc63837cb57620f8c8ddb47c9ff7da7e81`; proof script SHA-256 `61804a416f56884f3229fb25390babfd80ec2ec3c8f1fc841b6d3d163c783dd1`. Assignment-scoped `worker_check.py --complete` exited 0; `scoped-check.log` SHA-256 `5bb4aefa65602e8bec41d890aa02b6580f80e4b630b2ded76e329e6be78237f8`. An optimized Python (`-O`) rerun also exited 0; `stop-yield-optimized-cpu.log` SHA-256 `8ee56eadf643b432d499822dc2f96de9b9bbef631c5aa7e64bdfa3e9af6b87bb`. Required source validation uses explicit `ValueError` checks and remains active under `-O`. These are CPU diagnostic/static checks, not the strict ready gate.

## Exact remaining work

Review all accepted-recording source inventories and establish evidence equivalence only from retained artifacts. Review NRS-484B-257-1 stopping-reference hierarchy and officer/signal exceptions against the supplied exact text. Select only uncovered cases and build executable Native candidates, map/route/control acquisition, four-camera 30 s capture, current-runtime offline/positive/negative saved-processing proofs, semantic mapping, independent delivery/comparison audits and execution manifest. Run the assignment-scoped strict ready gate before changing status to ready. Actual motion, pixels and physical acceptance remain unclaimed.
