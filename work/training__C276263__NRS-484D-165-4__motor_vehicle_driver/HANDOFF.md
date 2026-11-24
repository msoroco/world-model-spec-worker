# NRS-484D-165-4 at C276263

Actor: `motor_vehicle_driver`. Frozen cell: `sloped_road` / `park` / `curb`.

Witness branch: Parked vehicle on sloped road.

Comparison variable: `parked_headlamp_beam`. Proposed physical probes: use depressed or dimmed lighted headlamps; use undimmed lighted headlamps. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C276263__NRS-484D-165-4__motor_vehicle_driver/assignment.json`, SHA-256 `bd55abb64e5cc2587217e454358991bba3d9af473fb46fcd8ff96e0c5f5afee7`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 sloped-curb lamp construction checkpoint

The exact supplied law governs lighted headlamps on a vehicle actually parked. The witness requires original beam elevation and intensity evidence and expressly cautions against treating a generic low-beam flag as legally equivalent to “depressed or dimmed.” `case-plan.json` now records that source boundary and maps each source observation term to original evidence requirements. A stationary command alone does not establish statutory parking rather than temporary loading or unloading.

`native/sloped-curb-road.xodr` authors a 4% road elevation profile, driving and curb-side parking lanes, sidewalk and curb reference. The two inline exact constructions in `draft-native/probe_a/construction.json` and `draft-native/probe_b/construction.json` each request 600 frames at 20 Hz for 30 seconds with the same parked pose, zero-speed request, lighted headlamps and four named source cameras. Probe A requests low-beam state; probe B requests high-beam state. `native/parked_lamps.py` rejects incomplete frame/time/source joins, absent original position or speed, mixed beam commands, and an original-Native claim without light-state readback and beam-pixel review. It does not claim requested low beam satisfies the statute.

Both exact constructions passed the pinned `runtime.py offline` CPU check; the commands and hashed logs are in `draft-native-manifest.json`. `native/audit_requests.py` independently verifies road grade, curb-side lane context, exact construction hashes, 600-frame fixed parking request and single beam-command difference. Its source-hashed diagnostic output is `native/request-comparison-proof.json`. These are authored requests only. The ordinary assignment-scoped `worker_check.py --complete` checkpoint passes. The assignment remains `partial` with unselected drafts because Native capture/controller and original light/pixel source sealing, actual parked-activity evidence, selected-case compatibility, actual process-saved, fallback candidates and independent acceptance/comparison audits remain unfinished CPU work. Physical beam realization, vehicle parking and legal outcome require original local evidence.
