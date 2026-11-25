# NRS 484B.627(1)(a) at C230259 — CPU delivery preparation

The fixed actor and cell are `motor_vehicle_driver`, `road` / `travel` / `other_vehicle`. The exact law and witness are in `case-plan.json` and frozen `inputs/`. Activation depends on slow operation that impedes traffic immediately behind, one highway travel lane in each direction, and enough paved width. Extreme-right placement and conditional NRS 484B.630 compliance are distinct. Speed, gap, duration and distance from the edge are measurements, not legal cutoffs. Public-highway status, actual causal impediment, sufficient paved width and NRS 484B.630 applicability require independent evidence.

## Constructed work

`build_draft.py` generates paired primary and `fallback1` Native CPU constructions under `draft-slow-traffic/` for `__controlled_1` and `__controlled_2`. The subject speed, follower policy, map, cameras and duration are common. Controlled_1 requests rightward movement; controlled_2 holds lane center. The shared fallback changes the initial follower gap from 18 m to 14 m only if early source evidence shows the follower remains more than 15 m behind. The one-lane-each-way OpenDRIVE has a 3 m right paved shoulder and an explicit edge. `native/runner.py` surveys it, runs the original Core and graph collector, captures 600 same-frame participant, body and controller samples, writes four runtime-named lossless cameras, and seals acquisition after restoration.

`finalize.py` requires the source trace, Native lane context, map, frame map, Core trace, original evidence and graph joins. It fully decodes the camera streams and writes source-hashed diagnostic measurements. `audit_comparison.py` independently checks fixed map, highway context, policy, time and camera sources while measuring rightward versus lane-center contrast. The two `measurement-controlled_*.json` contracts bind selected requirements to saved observations and specify a missing-context negative source. `delivery_audit.py` performs independent positive and negative source checks for each case.

## CPU proof results

- All four current primary and fallback offline constructions passed `runtime.py offline`.
- All four source-bound public compatibility receipts under `compatibility/` report `passed: true`, with positive and negative analysis logs. They used source-hashed 600-frame synthetic diagnostic fixtures.
- All four `saved-controlled_*-processing.json` receipts report `passed: true` and `recorded_only: true`, with original source checks and 600 decoded review frames. Each was captured and processed with the same draft-manifest identity. A separate replay using a different selected-manifest hash correctly rejected the frozen candidate identity; GPU capture must use its final manifest consistently.
- `physical_preparation.py --build` produced two synthetic physical and lifecycle proof receipts accepted by `execution_manifest.validate`. The selected `execution-manifest.json` validates against the current runtime.
- `semantic_delivery.validate` accepted the eight-stage canonical semantic chain and complete two-point controller sweep. `delivery_audit.py` positive and negative self-tests passed for both cases, and `delivery_handoff.validate_case` accepted both source-hashed contracts. Package compatibility and portable import checks passed.
- The exact command `.venv-cpu/bin/python worker_check.py --assignment training__C230259__NRS-484B-627-1a__motor_vehicle_driver --complete --require-delivery-ready` passed with exit 0 and `static_checks_passed: true` on 2026-11-25. `result.json` is `ready`, `readiness_kind: delivery_prepared`, with two selected cases.

These CPU results establish delivery preparation and source-bound synthetic diagnostics. Original Native motion, actual public-highway and paved-width status, causal impediment, pixels and legal conclusions remain for independent GPU delivery review. The first GPU delivery command is recorded in `result.json`.
