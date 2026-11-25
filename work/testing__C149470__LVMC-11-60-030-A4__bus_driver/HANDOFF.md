# C149470 bus loading preparation handoff

Status: partial. Seven exact cases and five planned comparisons remain source gated. The selected manifest is a diagnostic CPU draft; its source kind is synthetic and it is not an accepted original attempt.

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
