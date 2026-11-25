# testing__C158196__NRS-484B-257-2__motor_vehicle_driver

Status: ready for local Native delivery preparation. CPU strict assignment gate passed 2026-11-25. Historical source-inventory notes follow.

Exact law: NRS 484B.257(2) — Except when traffic is being controlled by a police officer or a traffic-control signal: The driver of a vehicle shall stop in obedience to a stop sign or yield in compliance with a yield sign, in compliance with the manner prescribed in subsection 1 [NRS-484B-257-1], prior to entering an intersection if a stop sign or a yield sign is erected at one or more entrances thereto although not a part of a through highway and shall proceed cautiously, yielding to vehicles not so obligated to stop or yield and which are within the intersection or approaching so closely as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Within-intersection instance plus unresolved approaching-hazard sweep..
Cell: C158196 (one_way_to_two_way_intersection, travel, traffic_light); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 9. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 9 exact law/actor ranges. These are unmeasured construction targets. 6 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 source-bound construction checkpoint

Six exact cases are in `case-plan.json` and symbolic Native lane/actor targets are in `case-specs.json`: within-intersection stop/yield, approaching counterpart near/far, and separately controlled signal/officer exceptions. Four comparisons declare fixed conditions and differences. The frozen demo-test accepted metadata only identifies two 900-frame cases; it does not establish these physical branches. `native_witness.py` has lazy source-gated road/device inspection before two-actor spawn and original-frame measurement of 900 synchronized 20 Hz body/control histories. It distinguishes within from approaching relations, verifies counterpart priority, stop-sign pre-entry speed, and leaves immediate-hazard legal judgment unresolved. `compare` rejects fixed-condition drift.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-2__motor_vehicle_driver/tests -v` passed 10 tests; `cpu-tests.log` SHA-256 `abafc7c33dad988489ff5aa02d1990bbccbd178c43c58290a8adca3980f09216`. Exact assignment `--complete` passed. Exact `--complete --require-delivery-ready` fails at `Preparation acceptance failed: partial/missing packages remain` because this result is truthfully partial.

Next CPU work: resolve actual C158196 Native map/device lane references and implement the CARLA adapter/runner and controllers; complete canonical semantic proposals, manifest, requirement dispositions, source-bound positive/negative compatibility receipts for each case, saved-only finalization and independent video/delivery/comparison audits. Retain the 9 judgment-range probe targets as physical planning targets, with impossible domain endpoints documented in `judgment-probe-plan.json`; do not infer a legal hazard threshold. Physical motion and camera coverage remain later GPU verification.

## 2026-11-25 construction and proof continuation

Six exact NRS 484B.257(2) delivery cases now have semantic proposals, source-hashed Native construction bundles, an original-site survey contract, CARLA adapter and controller, four-camera original capture, saved-only analysis, and measurement contracts. The within-intersection measurement retains the priority vehicle's occupied interval before ego entry, allowing a controller to wait until it clears. The analyzer keeps immediate-hazard and cautiousness legal judgments unresolved.

The current CPU suite passes 29 tests. All six primary and six fallback offline bundle checks pass. For each case, three synthetic measured physical outcomes and one Native-closure ordering test pass. Six diagnostic delivery checks pass four-view full decoding, sampled pixel comparison and synthetic motion/participant joins; six negative checks reject a missing camera source. These software fixtures claim neither original Native capture nor physical acceptance. Production delivery and pair-comparison auditors require sealed original sources, full original media, sampled original pixel joins, measured crossing and independent review.

The corrected 12-candidate end-to-end compatibility rerun and saved-only process-saved proof are in progress. Status remains partial until each exact compatibility proof and the scoped strict gate pass. The local physical handoff still needs an original reviewed C158196 site bundle, actual CARLA acquisition and independent original-source audit.

## 2026-11-25 exact CPU gate passed

The assignment passed `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete --require-delivery-ready` against the current pinned runtime. Six exact cases and four controlled comparisons are bound in `execution-manifest.json` and `case-plan.json`. All 12 primary/fallback offline checks, all 12 selected compatibility checks, six saved-only finalizations, 29 unit tests, six positive and six negative delivery component checks passed. The synthetic physical fixtures also passed three measured outcomes per case and one closure test per case. The negative delivery checks returned nonzero with the expected changed-source rejection. All software checks were source hashed; `result.json` is ready for `delivery_prepared`.

This is CPU package readiness. The local operator must supply `C158196_ORIGINAL_SITE_BUNDLE` with source-reviewed original map, lane, device, route and camera locations. Actual CARLA motion and full original four-view FFV1 capture require subsequent local execution. Production audits require independent review of sealed original source, video pixels, physical completion and each comparison's fixed geometry; synthetic diagnostic proofs do not establish those outcomes.
