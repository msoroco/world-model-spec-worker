# LVMC-11-52-070 at C385967

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_road` / `angle_park` / `angle_parking_designation`.

Witness branch: permitted angle-parking orientation.

Comparison variable: `angle_park_orientation`. Proposed physical probes: park front toward lawful traffic direction; park front opposite lawful traffic direction. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C385967__LVMC-11-52-070__motor_vehicle_driver/assignment.json`, SHA-256 `7e2ea624713eebcfbb8a5f65515fe98c43b02be4232ce507370ec96c707a6052`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact draft construction and CPU proof

The current frozen assignment hash is `fbd358a4a2f996803ab49730b88f8a3ab4b8d15d6781c35ce2df8c96766d1574`; the earlier source hash above is historical. `native/angle-bay-road.xodr` authors a northbound one-way driving lane, angle-parking bay and proposed sign. `native/angle_park.py` checks the exact case and source contract, 600 joined rows, parked center and speed, four camera geometries, and the sign of the front vector projected onto the lawful road tangent. It deliberately defines no statutory angular tolerance. The City Traffic Engineer's permission decision is a separate source requirement and is not inferred from the authored sign.

`draft-native/probe_a/construction.json` SHA-256 `c3b82d52c9351e8ac3ad7bf8ea379004e50db048e3d25bc60b6901fe0fe89efa` requests a front yaw of 45 degrees with the northbound flow. `draft-native/probe_b/construction.json` SHA-256 `63b12a4ea74f86954025982adc9a6eecde9c5564670712b26b0eee8fb192396a` requests 225 degrees against it. Both are 30 seconds, 20 Hz, 600 frames, with the same bay center, zero speed and four named source cameras. Pinned `runtime.py offline` returned `offline_passed: true` and `simulation_started: false` for both; see `native/proof-probe-a.log` and `native/proof-probe-b.log`. `native/request-comparison-proof.json` SHA-256 `4d1e1eacb15d856c6c4b1621150afa5d9031250290d144ef4b8bc402352a0bc6` independently checks exact source hashes, road topology and the sole orientation difference.

These are unselected authored requests. They do not prove that angle parking is legally permitted at the place, that the sign exists in original Native observation, that the vehicle actually stood or parked in an angle bay, or that the original body front faces with or against lawful traffic. Native readback, permission evidence, four candidate compatibility recipes, selected process-saved fixtures and independent acceptance audit remain to be built. Status stays `partial`.

## 2026-11-25 selected CPU delivery package

The two exact cases now have original Native acquisition code, four-view 20 Hz camera capture, 600-frame body and source joins, saved-only finalization, and distinct primary and service-brake fallback constructions. The City Traffic Engineer designation remains a separate required external source and is never inferred from the authored angle-parking sign. The front-direction measure uses the observed vehicle front projected onto the lawful one-way direction; it does not introduce a statutory angle tolerance. No original Native capture or legal verdict is claimed.

All four selected construction candidates passed pinned offline and source-shaped compatibility checks, including full decode, native validation, measured channels, and a missing-permission-source rejection. Each case passed canonical recorded-only processing with a 600-frame positive and a missing-authority negative; those processing receipts are synthetic CPU diagnostics. The independent delivery audit passed its source-shaped positive and rejected an out-of-bounds reviewed pixel box. The paired comparison checked fixed scene conditions and opposite observed directions, then rejected missing permission evidence. The semantic index contains three source topics and passed direct validation.

The exact assignment-scoped strict gate passed with `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR`, `MPLCONFIGDIR`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/`:

`.venv-cpu/bin/python -B worker_check.py --assignment training__C385967__LVMC-11-52-070__motor_vehicle_driver --complete --require-delivery-ready`

Stable package hashes: `execution-manifest.json` `4f133eccb0d6e9631756bc49f5c182d61ab3a4eed416c12885f0ce3e338f48bc`; `construction.json` `379e56cb2d418615e5272737707c586c240526502173b02531d27f8a89d8750f`; `result.json` `84d0e60480ad57879dbba9ca5dd0bee4ebe151c7f2a60bc9ffca85fec2ff2433`; `proposals/semantic-index.json` `7b0efda02f56c12e13810e59ec2955dd903695df39a65c3fc44c96aaeb9b60b3`. The saved processing positive hashes are `e1757bcb4e73b48d12c7daf6006b8d5e982480f4431f949f3cefb274789f35b9` for A and `13cf42b053fe0af043f83f2cdffb208556fd32c84884b0878caf8595fb9423fa` for B.

Next on GPU: obtain and independently review the actual City designation, marking, lawful traffic direction, and parked pose; decode all original camera frames; review the sign, bay, vehicle front, and direction in actual pixels; then run local full-train acceptance and the paired source-bound comparison. Keep legal outcome unresolved until those sources exist.
