# C149470 bus loading preparation handoff

Current status: ready for CPU delivery preparation. Thirteen exact selected cases and nine controlled comparisons are prepared; original motion, source review, video acceptance and legal judgment remain local work. The dated sections below retain the progression from the earlier partial checkpoint.

## Current CPU package

`bus_curb.py` constructs and measures non-tour bus entry, stopped passenger or baggage loading, right-front-wheel point-to-curb distance with uncertainty, approximate-parallel observation, and separate traffic movement at 20 Hz for 900 frames. The three bus-stop targets are 0.4472, 0.4572, and 0.4672 m around the statutory 0.4572 m boundary. Four other cases cover bus stand baggage, passenger zone unloading, origin loading, and destination unloading. Legal disposition of approximate parallel and undue impediment remains unresolved.

`diagnostic_runner.py`, `build_diagnostic_bundles.py`, `build_runtime_compatibility.py`, `analysis.py`, `build_selected_draft.py`, and `prove_physical_diagnostic.py` produce seven exact synthetic Native-shaped diagnostic bundles and source-specific measurements. All seven pinned offline, positive and missing-source compatibility, recorded-only saved processing, selected offline, and diagnostic physical-preparation checks have passed. The seven selected compatibility receipts and physical receipts are bound in `execution-manifest.json`. `build_semantic_draft.py` creates the canonical seven-stage semantic chain, and direct `semantic_delivery.validate` passes with seven selected cases. `branch_coverage.validate_evidence` passes. Focused unittest passes 10 tests.

`reviewed_source.py`, `delivery_audit.py`, and `saved_finalizer.py` are production source gates. The independent auditor requires a reviewed site packet, twelve source hashes, retained original 900-frame rows, and four separately decoded 900-frame camera videos. Five comparisons require exact original audit reports and fixed source equality. `prove_original_delivery.py` exercises the seven delivery contracts with explicit mock-only positive wiring and missing-reviewed-source negative rejection; direct `delivery_handoff.validate_case` passes 7/7. These proofs make no original, physical, or legal acceptance claim.

`build_fallback_draft.py` creates one diagnostic fallback per exact case for the concrete risk that the primary bus approach overshoots the narrow curb target or does not stabilize for twenty consecutive stopped-loading frames. It shifts only the bus approach start two meters upstream and retains the terminal curb target, loading activity, traffic route, timing, cameras, case identity, and recording description. Seven fallback offline checks and seven pinned positive/negative compatibility checks pass. Direct `candidate_constructions.validate` passes 7/7 with `cpu-nov25-fallback-offline-*.log`, `cpu-nov25-fallback-compat-*.log`, and `proofs/fallback1-*/` receipts. Original site review must decide whether the measurable fallback trigger occurred.

## Exact remaining gate

Direct `execution_manifest.validate` rejects the selected draft with `Expand sweeps with the main implementation before manifest generation`. The two sweep specs in `proposals/cases.json` remain incomplete because no reviewed original site, original attempt, or independently reviewed qualitative range is supplied for `approximately parallel to the curb` and `not to unduly impede the movement of other vehicular traffic`. Do not set `sweeps_expanded` on synthetic measurements. Direct candidate, delivery and physical-preparation validators each pass 7/7. Direct semantic and branch validators pass. `execution_manifest.validate` fails exactly at the unexpanded sweep check. The exact scoped strict command exits 1 at `Preparation acceptance failed: partial/missing packages remain` because `result.json` remains truthful partial. Scoped `worker_check.py --assignment ... --complete` exits 0.

`source-acquisition-contract.json` specifies the missing original site packet: jurisdiction, bus class, tour exclusion, operator, location boundary/designation, signs, curb geometry, right-front-wheel, bus route, loading activity, and traffic route with source bytes, citations, reviewers and hashes. It also specifies original frame identities, bus/traffic motion, wheel and curb geometry, location/loading context, position uncertainty, and 900 frames of each of four camera streams. The current synthetic route and camera fixtures cannot supply those original facts.

## Reproduction

Set `SCENARIO_PIPELINE_OUTPUT_ROOT` and `TMPDIR` under `.runtime-work/c149470/` before direct runtime imports. The pinned commands for every case are recorded in `result.json.tests` and the selected manifest. The exact scoped gate is:

`.venv-cpu/bin/python worker_check.py --assignment testing__C149470__LVMC-11-60-030-A4__bus_driver --complete --require-delivery-ready`

No physical capture or legal acceptance is claimed. Continue from reviewed original sources and independent judgment ranges, then regenerate the selected executable construction, expand the two sweeps, rerun all source-bound CPU proofs, and only then assess strict readiness.

## Stable checkpoint receipts

- Selected draft manifest SHA256: `40aba2a08dcc202e187b4de09bfd2c0ab0efbc727c95da3b885e0c0809477f6b`.
- Direct validator log: `cpu-nov25-direct-selected-validators.log`.
- Scoped complete static log: `cpu-nov25-static-final.log`, exit 0.
- Exact scoped strict log: `cpu-nov25-strict-final.log`, exit 1 on partial status.
- `result.json` lists 58 successful CPU proof logs with current SHA256 values.

## 2026-11-25 source-gated engineering grid continuation

The two previously incomplete qualitative sweeps now have fixed physical engineering requests: bus approach heading 0, 4 and 8 degrees, and separate traffic route lateral offset 2, 3 and 4 m. These are requested geometry points, not legal cutoffs. `build_semantic_draft.py` uses pinned `expand_sweeps` to create six exact selected cases; `bind_source_sweeps.py` binds them into `case-plan.json`, now 13 selected cases and seven comparisons. Canonical semantic validation passes 13/13. Original stopped-loading bus-curb angle and separate traffic speed remain unmeasured until original Native capture. The revised acquisition contract requires reviewed original curb tangent, bus pose, other-vehicle route and motion.

`native_capture.py` provides a source-sealed 900-frame 20 Hz Native acquisition path, four original camera streams, explicit attestation gate and owned-actor cleanup. `diagnostic_runner.py` requires a reviewed site packet and adapter module for capture; synthetic `--check` remains diagnostic only. A mock adapter positive and non-attested negative test pass, with 11 focused tests overall. The seven-comparison CPU wiring probe passes and rejects synthetic source promotion. `selected_delivery.py` and `selected_comparison.py` are original-only independent audit entrypoints. Current-hash pinned compatibility is running against the final 13 construction hashes under `.runtime-work/c149470/grid5-*`; selected receipt binding, saved processing, physical and delivery refresh, exact scoped strict and queue proposal remain CPU work. `result.json` stays partial.

## 2026-11-26 selected delivery preparation

Thirteen exact selected cases, thirteen source-gated fallback candidates, and seven original-only comparisons are bound in the canonical plan, proposal, manifest and assignment-local queue proposal. Both qualitative sweeps use three controlled engineering geometry requests; 0/4/8 degree bus headings and 2/3/4 m separate traffic offsets are probe inputs, not legal thresholds. Production capture requires reviewed site and Native adapter attestation, 900 joined 20 Hz frames and four original camera streams. Original approximate-parallel and undue-impediment judgment remains unresolved.

All thirteen selected primary/fallback offline runs, positive/missing-source compatibility proofs, recorded-only saved processing, three-state physical/lifecycle preparation, and positive/negative independent delivery audits passed. Seven original-only comparison wiring checks passed on mock fixtures, rejecting synthetic promotion. Direct execution manifest, semantic, delivery, compatibility and branch validators passed. Thirteen focused tests and the scoped complete static check passed. The selected root and all case/fallback bundles are materialized. The exact strict gate is `.venv-cpu/bin/python worker_check.py --assignment testing__C149470__LVMC-11-60-030-A4__bus_driver --complete --require-delivery-ready`.

The exact scoped delivery-ready gate passed on the 13-case selected package; `cpu-grid-strict-initial.log` records the first exit-0 proof. The returned package remains CPU delivery prepared. Local original-site acquisition, actual CARLA motion/video acceptance, and legal judgment are still required.

## 2026-11-27 interior sweep comparison repair

The batch branch matrix exposed two selected engineering sweep cases that had no comparison: `parallel_source_review-0001` and `traffic_impediment_source_review-0001`. `case-plan.json` now adds `parallel_engineering_below_interior` (the 0 versus 8 degree requested bus-route heading cases) and `traffic_engineering_interior_above` (the 4 versus 3 m requested separate-traffic-route offset cases). These are engineering requests, not statutory cutoffs. The independent `delivery_audit.audit_comparisons` permits exactly the relevant original route source to change for each named sweep comparison, while requiring the fixed original source inventory, unresolved legal status, original source kind and measurement provenance. `prove_grid_comparisons.py` exercised all nine mock-only positive paths and synthetic-source rejection; 13 focused tests passed. `queue-proposal.json` now contains all nine commands. The two small `queue-comparison-proposal-*.json` files each carry one new dispatch row and its original-only command catalog entry for lead integration; existing case rows remain unchanged. The exact scoped strict gate passed, recorded in `cpu-matrix-strict.log`. Actual source acquisition and physical judgment are still pending local execution.
