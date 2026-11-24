# LVMC-11-52-300 at C229398

Actor: `nonmotor_vehicle_operator`. Frozen cell: `road` / `park` / `curb`.

Witness branch: Qualifying nonmotor vehicle parked within the nighttime window.

Comparison variable: `night_parking_duration`. Proposed physical probes: park nonmotor vehicle less than thirty minutes; park same vehicle more than thirty minutes. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator/assignment.json`, SHA-256 `4b5bd39e7e07cd611b5d4fb38ff8983f109dd2305f4336d293bdc83f40d8d1dc`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

CPU source-shaped measurement checkpoint: `native/night_parking.py` (SHA-256 `afb5742da41e9a1f3dea0ed6d9c7f40c211d85b043fd8e3e6b95578c4748a1b9`) consumes a retained 20 Hz frame map and source-hashed classification, street geometry, parking activity, and civil-clock packets. It derives stationary on-street time inside the local 01:00-06:00 window, requiring a contiguous episode strictly over 1,800,000 ms. It rejects incomplete frames, bad 20 Hz joins, missing source packets, and stale hashes. The source-observation mapping and unresolved factual requirements are in `native/measurement-contract.json` and `case-plan.json`.

`.venv-cpu/bin/python runtime.py preflight` exited 0. `MPLCONFIGDIR=.runtime-work/mplconfig .venv-cpu/bin/python work/training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator/native/prove_night_parking.py` exited 0. The test script SHA-256 is `411b25397e704a0dcbcd216993265c864221590aadd0a12985a9e7c47e80a250`; `native/night-parking-proof.json` SHA-256 is `b0d3ee68ef961f7d4a6ba4b2f8772f5927fb8d225e595d0cc7cad2e79be7256f`. It tested 29:59, exactly 30:00, 30:01, motor-vehicle exclusion, outside-window timing, broken frame map, stale source, and mismatched clock packet. All packets were invented diagnostic fixtures, so no Native motion, real device class, legal parking status, or physical compliance is established.

Unselected exact Native draft for `probe_b`: `native/build_draft.py` inlines `native/draft_runner.py`, `native/parking-road.xodr`, a 36,043-frame 20 Hz phase request, and four named RGB cameras into `draft-native/construction.json` (SHA-256 `1bfe8336fa7b55e0e194f761eea0699793c37ecccc2ad0ca1771cb9b4eb4159e`). `draft-native-manifest.json` SHA-256 is `b35366f805c5c58420d985b35b05a931665e1bd94bb9d3bd62a4806362ba0324`. Pinned `runtime.py offline --manifest work/training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator/draft-native-manifest.json --case training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator__probe_b --output .runtime-work/C229398-night-parking/offline-probe-b-v1` exited 0; `native/draft-offline.log` SHA-256 `aad8e508a6ea54a2c78b89c46d79e4506e9b0089a49908b183b2bab3ccc9f98f` and `native/draft-offline-proof.json` SHA-256 `d99abbae30dc91218adfbb902459ac20e550be8e18803fd8c6dc14f2377d89a4`. The CARLA crossbike blueprint is an engineering stand-in only; no source establishes its legal nonmotor classification. The runner is a Native request prototype, not a selected or physically tested delivery case.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell, including a source-proven qualifying nonmotor vehicle and over-30-minute continuous capture; implement four cameras and selected exact cases with distinct candidates; run pinned offline, compatibility, saved-only, comparison and independent audit proofs. Resolve public street access, city limits, responsible person, parking purpose and temporary loading from real sources. Set ready only after those proofs and assignment-scoped strict gate pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
