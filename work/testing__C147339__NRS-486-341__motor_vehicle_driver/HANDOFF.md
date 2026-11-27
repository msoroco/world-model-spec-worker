# C147339 NRS 486.341 delivery handoff

Assignment: `testing__C147339__NRS-486-341__motor_vehicle_driver`
Status: `ready`, `delivery_prepared`
Scoped strict gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C147339__NRS-486-341__motor_vehicle_driver --complete --require-delivery-ready` exited 0; `cpu-strict-check.log` SHA256 `53f08c99fc6b2c3c3693b5cd44b9deb23d14e20ab4b3767827699d2edbc47f32`.

## Exact source and coverage

NRS 486.341 protects a driven motorcycle or moped's full use of its occupied traffic lane on a highway. The assigned cell is a one-way multilane road with a motor vehicle driver. Frozen accepted recordings for this assignment: 0. Frozen judgment-range entries: 0. `case-plan.json` records the source and witness review, five exact cases, four controlled comparisons, and the mandatory capture observations. The package measures body intrusion and protected motion without inventing a numeric legal cutoff or claiming a legal verdict.

The five cases are `motorcycle_adjacent_clear`, `motorcycle_edge_encroach`, `motorcycle_deep_encroach`, `moped_edge_encroach`, and `motorcycle_stationary_edge`. The four comparisons isolate lane edge intrusion, intrusion depth, protected vehicle class, and driven activation. `lane_use.py` checks source-declared highway/lane/vehicle dimensions and routes, constructs two distinct actors, and verifies 900 consecutive 20 Hz original-frame rows. `original_capture.py` specifies synchronized four-view FFV1 capture and source readback. `analysis.py` is a saved-only finalizer.

## CPU proof chain

- Six assignment unit tests and pinned runtime preflight pass; their hashes are bound in `result.json`.
- All five semantic proposals pass pinned validation across the required stages.
- All five primary and five risk-based fallback candidates pass exact offline checks.
- All five cases pass complete-motion, incomplete-motion, and missing-evidence physical/lifecycle checks.
- Ten exact source-shaped compatibility candidates pass positive and negative proofs.
- Five saved-source delivery audits pass positive diagnostic integrity checks and negative original-source rejection checks.
- Four comparison audits pass positive fixed-condition checks and negative identity checks.
- All five diagnostic sources pass recorded-only `process-saved`, with original inputs preserved.
- The scoped strict assignment gate exits 0 after revalidating the bound receipts and static contract.

`execution-manifest.json` SHA256: `124f51e3031cb21cc070289b9875a4541b7e7f4dc25b5018cec054c4e3fd7944`. `gpu-queue-proposal.json` SHA256: `12bf4fd9bab63cca063d8d5acbb6c28ac4bec230569dda21ed822c5d2812da32`. `result.json` SHA256: `b60a4496598c0de7f95fde601b0d298f412125e2ce48e5dc7ac081956bdfb2c6`.

## Native delivery boundary

The queue proposal contains five case-specific prepare, execute, accept, owner-release, and postprocessing commands plus four comparison commands. Every command binds its exact case ID, including owner release. Before Native capture, independently review the original public highway and OpenDRIVE source, motorcycle/moped classification and exclusions, actor dimensions/routes, and camera poses. During Native capture, inspect actual two-actor motion, 900 synchronized frames, four original video streams and physical completion. Independent source-bound review must decide whether the facts deprive the protected vehicle of full lane use. CPU diagnostic receipts make no original-pixel or legal finding. All scratch output belongs under `.runtime-work/`; original Native evidence remains external to the returned package.
