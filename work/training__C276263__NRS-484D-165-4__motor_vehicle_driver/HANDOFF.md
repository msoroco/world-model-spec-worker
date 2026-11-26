# NRS-484D-165-4 at C276263

Actor: `motor_vehicle_driver`. Frozen cell: `sloped_road` / `park` / `curb`.

Witness branch: Parked vehicle on sloped road.

Comparison variable: `parked_headlamp_beam`. Proposed physical probes: use depressed or dimmed lighted headlamps; use undimmed lighted headlamps. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C276263__NRS-484D-165-4__motor_vehicle_driver/assignment.json`, SHA-256 `ad352226bc94145906f84dcfeea368d5da7f2268335d3dfac4f6d910bdf1502e`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 sloped-curb lamp construction checkpoint

The exact supplied law governs lighted headlamps on a vehicle actually parked. The witness requires original beam elevation and intensity evidence and expressly cautions against treating a generic low-beam flag as legally equivalent to “depressed or dimmed.” `case-plan.json` now records that source boundary and maps each source observation term to original evidence requirements. A stationary command alone does not establish statutory parking rather than temporary loading or unloading.

`native/sloped-curb-road.xodr` authors a 4% road elevation profile, driving and curb-side parking lanes, sidewalk and curb reference. The two inline exact constructions in `draft-native/probe_a/construction.json` and `draft-native/probe_b/construction.json` each request 600 frames at 20 Hz for 30 seconds with the same parked pose, zero-speed request, lighted headlamps and four named source cameras. Probe A requests low-beam state; probe B requests high-beam state. `native/parked_lamps.py` rejects incomplete frame/time/source joins, absent original position or speed, mixed beam commands, and an original-Native claim without light-state readback and beam-pixel review. It does not claim requested low beam satisfies the statute.

Both exact constructions passed the pinned `runtime.py offline` CPU check; the commands and hashed logs are in `draft-native-manifest.json`. `native/audit_requests.py` independently verifies road grade, curb-side lane context, exact construction hashes, 600-frame fixed parking request and single beam-command difference. Its source-hashed diagnostic output is `native/request-comparison-proof.json`. These are authored requests only. The ordinary assignment-scoped `worker_check.py --complete` checkpoint passes. The assignment remains `partial` with unselected drafts because Native capture/controller and original light/pixel source sealing, actual parked-activity evidence, selected-case compatibility, actual process-saved, fallback candidates and independent acceptance/comparison audits remain unfinished CPU work. Physical beam realization, vehicle parking and legal outcome require original local evidence.

## 2026-11-25 original-source acquisition and finalizer checkpoint

`native/runner.py` now has a CARLA-lazy `--capture` path. It creates the authored 4% OpenDRIVE sloped road, verifies curb-side parking lane -2, spawns the parked motor vehicle, requests the exact probe beam state, reads back original light-state bits, velocity, body footprint and lane ID on each of 600 ticks, and synchronizes all four source cameras through `FrameMap`. It requires an exclusive idle world, restores the previous world in cleanup and seals only a complete capture. The result deliberately leaves original parked-activity, beam-pixel and vehicle-class reviews pending. The fake-world 600-tick and tick-failure lifecycle tests in `native/test_capture_lifecycle.py` pass; log SHA-256 `3d38282c751732c9af3f486d091e6fa34e0ebb84d1c7f998396144e5ec25a4f7`. This is software proof, not actual CARLA realization.

`native/parked_lamps.py` now separates original light readback, curb lane and body footprint from authored requests and rejects request relabeling, missing beam state, missing activity, missing footprint and absent source-hashed pixel review. The four source-meter tests pass; `native/source-meter-tests.log` SHA-256 `5d8a174d448d59185fd227bcbab9c964e39b10a9c2e28965972cfb0c833dd854`. `native/finalize_original.py` joins the sealed Native rows, frame map, four original video references, reviewed lamp/parking rows and verified review files by hash. It requires the full original parked and lighted window and records beam elevation/intensity ranges without a legal threshold or verdict. The four synthetic fixture tests pass; `native/finalizer-tests.log` SHA-256 `f63855a03a978872be214b8d83a9bdae45fc7e2680e2224042aa4b3f94ad9f3e`. The positive fixture is explicitly labeled synthetic.

Both exact draft constructions were rebuilt with the capture and finalizer code, and current-runtime offline checks passed: `native/proof-probe-a.log` SHA-256 `9e24e5e2f1006cbee4de1a1acd963a954740e43dd51aaa406716490ffabf105b`; `native/proof-probe-b.log` SHA-256 `e8cadde1086d8d2db80634a10ed942861ccb93d08f93714f39b01e853106b0de`. The request comparison was rechecked after the construction change: `native/request-comparison-proof.json` SHA-256 `da59f9f2863b5d52e2cf5dd0e329576b378615e6fd4229c0f7d739cdbc34ddbc`. `.venv-cpu/bin/python worker_check.py --assignment training__C276263__NRS-484D-165-4__motor_vehicle_driver --complete` passed as a partial checkpoint.

The exact CPU work still needed is selection of both cases with source-hashed measurement contracts and recipe, positive and missing-source compatibility, recorded-only process-saved proof, semantic proposals, physical/lifecycle and independent delivery/comparison audits, and risk-based fallback construction if original parking, source camera or beam review fails. Do not label low-beam control or synthetic beam measurements as the statutory phrase “depressed or dimmed.” Set ready only after `.venv-cpu/bin/python worker_check.py --assignment training__C276263__NRS-484D-165-4__motor_vehicle_driver --complete --require-delivery-ready` passes.
