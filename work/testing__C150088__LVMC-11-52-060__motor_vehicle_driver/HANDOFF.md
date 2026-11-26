# testing__C150088__LVMC-11-52-060__motor_vehicle_driver

Status: partial CPU delivery package. Five exact delivery cases and three controlled comparisons are selected; strict readiness is pending independent audit proofs.

Exact law: LVMC 11.52.060 — In no case shall any part of any vehicle, part of the load of such vehicle or trailer attached to such vehicle, project into the street more than fifteen feet measured on a line at right angles to the curb.
Assigned branch(es): complete physical projection.
Cell: C150088 (one_way_road, park, curb); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150088__LVMC-11-52-060__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The full physical projection includes any vehicle part, load part or attached trailer part. `case-plan.json` now defines five unselected cases spanning below/equal/above fifteen feet and load/trailer controlling parts, with three isolated comparisons. No accepted recordings are in the frozen inventory.

`projection_measurement.py` binds an original source hash, validates complete part outlines and curb/street-side geometry, then computes the largest perpendicular projection into the street. Fifteen feet is exactly 4.572 m. Five synthetic CPU tests cover vehicle, load, trailer completeness, curb direction and ambiguous street side. This is a geometry proof, not evidence of physical realization.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `34bc7aef90a65f3487eb1c1421d209dfcc7632c959a6ec7060c809f1fb10bb0f` |
| `projection_measurement.py` | `62762ed0e21030c65719f67d6f07845835ab5bf19e0b72d270a72fcf48981b87` |
| `tests/test_projection_measurement.py` | `2c12c0af4506bfaa250f888829dd7df2925f466524774972738d22839eb8a2c5` |
| `preflight.log` | `226c17ac1c2b7d8404d84edac85fa77170ea3e7d5f55022158154a89ba4ae7f0` |
| `unittest.log` | `1f171ab732a00e5de83833ce9c2a5559708a923870ff9bc5fc88e53d375c785d` |
| `static.log` | `e8e7ffebb446fd4a467b09ff16d18f73bbb7cb9fda43955f11973121d19bb0e5` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: build and read back parked vehicle, load and trailer configurations with actual curb geometry; save original complete outlines; implement selected-case finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA realization and visibility follow CPU readiness.

## 2026-11-26 source-bound CPU progress

Five exact cases (`vehicle_below`, `vehicle_equal`, `vehicle_above`, `load_above`, `trailer_above`) and three comparisons retain the single assigned C150088 curb cell. The statutory fifteen-foot boundary is exactly 4.572 m. The 0.08 m construction/readback tolerance and parked-dwell drift allowance are engineering checks only; they do not classify equality under the law.

`execution-manifest.json` binds ten immutable constructions (five primaries and five fallback1 at a different same-curb parking station), each with an exact offline receipt and positive/negative source-bound compatibility receipt. All ten offline and ten compatibility runs passed on the current pinned runtime, exercising the bundled finalizer, Native validation, Lean decode, four-camera media, and missing original projection history rejection. `proposals/semantic-index.json` and its five stage files pass `semantic_delivery.validate`. `physical_completion.py` has three CPU outcomes and lifecycle source proofs per case. Five `runtime.py process-saved` runs passed from diagnostic attempts with original sources unchanged; these prove saved-only software behavior, not real Native capture.

Case-specific fallback triggers are in the manifest: original pixel and Native readback audits must reveal masked controlling corners, curb references, or attachment/hitch visibility before changing from the primary 15 m curb station to the 18 m same-curb station. Perpendicular targets and all linked comparison variables remain fixed. Synthetic media and fixture projection values do not establish physical visibility or legal acceptance.

The package remains partial because the independent source-bound delivery audit, its positive/negative CPU tests, and the controlled comparison audit are unfinished. Resume with these audit implementations, bind each exact case `delivery_acceptance`, run focused tests and `.venv-cpu/bin/python worker_check.py --assignment testing__C150088__LVMC-11-52-060__motor_vehicle_driver --complete --require-delivery-ready`, then have the lead independently rerun before shared queue integration. Keep scratch and temporary files under `.runtime-work/`; use `PYTHONDONTWRITEBYTECODE=1`.

## 2026-11-26 exact scoped strict handoff

The earlier partial checkpoint above is superseded. Five exact cases and ten primary/fallback constructions have passed source-bound offline and positive/negative runtime compatibility CPU proofs. Five physical-completion and saved-processing fixture chains, five positive/negative independent delivery audit probes, and three positive/negative fixed-condition comparison audit probes passed. All generated test media and fixture visibility review remain synthetic CPU evidence; original Native 900-frame capture, actual four-camera pixel visibility, legal review, and local GPU acceptance remain for delivery execution.

The delivery auditor now binds the saved finalizer result from `processing.json` to the sealed original attempt, because Native capture seals source files before saved finalization. The normal audit requires original Native provenance, 900 joined frames, four original camera files and decoded pixels, curb and controlling-part visibility, complete parked-assembly mechanics, owner release, and unchanged source hashes. The 0.08 m engineering construction/dwell tolerance stays separate from the 4.572 m statutory boundary.

`execution_manifest.validate`, `semantic_delivery.validate`, all five `delivery_handoff.validate_case` calls, and `package_compatibility.check_receipts` passed. The exact strict assignment command exited 0 after setting `result.json` ready. Lead should rerun independently before shared queue integration. Scratch and temporary output are under `.runtime-work/c150088-nov26/`.

- `result.json` SHA256 `afb21a0bfc10c6ec2442a0bf5f49d99f444304462ca8563b2c39b6e810d77aab`
- `case-plan.json` SHA256 `42b7541af9d33ba614323af02c4e3afce6078df2b0d64098b6594be20685f3a5`
- `execution-manifest.json` SHA256 `33413f548c8587b072245df30e624f023bfad011bd5bd613027f54a9d95b2aa7`
- `delivery_audit.py` SHA256 `6cff109308ee1d59cf3be3827e9a623971571486db726e62447efa991db85395`
- `comparison_audit.py` SHA256 `2a3fde6f44f9c9c468f5dfaed0457e8c53fd760446d2a89405d92a6bb47a47b6`
- `cpu-scoped-strict-pass.log` SHA256 `3b6cb0b61ca1b6916b33669e3be3a243d417e9baf884d0d32bf42b68d4853280`

## 2026-11-26 exact GPU queue proposal

`gpu-queue-proposal.json` contains five exact Native case rows and three comparison audit rows. Each case includes canonical prepare, execute, accept, capture, owner attestation, saved processing, original source audit, and fallback1 preparation commands. The source audit runner decodes every saved primary frame with the source-hashed pixel checker before checking sealed original projection, Native lifecycle, and visibility review; its report is separate from the canonical local acceptance audit. The three comparison commands read only the exact source audit reports.

All 43 queue commands passed `bash -n`; each case and fallback command was checked against its exact manifest case and candidate, and comparison commands against the three plan comparisons. `source_audit_runner.py --help` passed; the scoped strict assignment gate was rerun after adding the proposal and passed. The original reviewed site packet and adapter, operator owner release, original visibility review, canonical local acceptance audit, and actual GPU capture remain delivery-time inputs.

- `gpu-queue-proposal.json` SHA256 `b92d9df31351060b489d9e2e6b0ebf907c9cd2005a81b8983e859aece55cc557`
- `source_audit_runner.py` SHA256 `1eca3be951632913fe684c27e65267038c3d05ab75d3e615c7767f6db3821663`
