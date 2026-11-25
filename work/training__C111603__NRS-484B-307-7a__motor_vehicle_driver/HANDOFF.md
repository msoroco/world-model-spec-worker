# NRS-484B-307-7a at C111603

Status: partial; source-bound arrow and other-vehicle timing requests pass pinned CPU offline checks.

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `turn` / `other_vehicle`.

Exact source: NRS 484B.307(7)(a). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Other-traffic yield duty.

Controlled variable: `yield timing under flashing yellow turn arrow`. Requested pair: turn on flashing yellow arrow after yielding to lawful users; turn on flashing yellow arrow ahead of lawful user. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 1. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Open work: Two source-bound 30-second turn requests and their offline proofs now exist. Original Native acquisition, saved processing, compatibility and physical/legal review remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Arrow may be displayed alone or with other indications; only its indicated movement or one permitted by a concurrent indication is allowed. Pedestrian and other-traffic yield duties are separate branches.

## Flashing-yellow arrow and other-traffic construction checkpoint, 2026-11-23

`native/request.py` binds the frozen NRS 484B.307(7)(a) text, authors an intersection with one requested flashing-yellow right arrow, and generates two 600-frame/20 Hz motor-vehicle right-turn requests. The arrow program and other-vehicle route are identical; only ego release changes. The requested first entry is frame 325 after the other vehicle has cleared the intersection, versus frame 205 while that vehicle is within it. Five changed-source cases reject: truncated frame inventory, altered arrow, changed other route, fabricated lawfulness and fabricated Native observation. Both exact draft constructions pass pinned `runtime.py offline`; see `yellow-arrow-cpu-proof.json` for hashes.

This proof concerns requested motion only. Arrow authorization/facing and actual flash pixels, original vehicle motion, other-traffic lawfulness, pedestrian presence and cautiousness are unverified. No legal right-of-way conclusion follows from temporal occupancy. Remaining CPU work: implement four-camera Native acquisition, saved-only measurement/finalization and positive/negative compatibility, physical-risk fallbacks, independent audits, the separate pedestrian and concurrent-indication branches, and strict selected delivery.

## Current-v2 retained-source CPU diagnostics, 2026-11-24

Two exact 600-frame source-hashed unselected diagnostics now exercise the pinned current-v2 public pipeline. `build-current-v2-primary.py` and `build-current-v2-contrast.py` regenerate their construction, source rows, fixture recipe, measurement contract and manifest. The retained `turn-history.jsonl` preserves the requested flashing-yellow arrow, ego turn and other-vehicle frame timing. `native/finalize_v2.py` and `native/finalize_v2_contrast.py` measure the frame/time joined request from saved sources. The first requested ego intersection entry is frame 325 after other passage in controlled_1; controlled_2 requests entry at frame 205 while the other vehicle remains inside. These are synthetic request measurements, not findings that either participant is lawful or the arrow physically governs the ego.

Run with `PYTHONDONTWRITEBYTECODE=1`, `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/owner198"`, and `TMPDIR="$PWD/.runtime-work"`. For each `LABEL` of `primary` and `contrast`, pair its `current-v2-LABEL-manifest.json` with exact case `training__C111603__NRS-484B-307-7a__motor_vehicle_driver__controlled_1` or `_controlled_2`, respectively. The public sequence is `runtime.py offline --manifest MANIFEST --case CASE --output .runtime-work/owner198/current-v2-LABEL-offline --python "$PWD/.venv-cpu/bin/python"`, then `runtime.py compatibility --manifest MANIFEST --case CASE --output .runtime-work/owner198/current-v2-LABEL-compatibility --library runtime/pipeline/library --validator .runtime-work/decoder-update16/.lake/build/bin/adapterCheck`, then `runtime.py process-saved --manifest MANIFEST --case CASE --attempt .runtime-work/owner198/current-v2-LABEL-compatibility --output .runtime-work/owner198/current-v2-LABEL-saved --library runtime/pipeline/library --validator .runtime-work/decoder-update16/.lake/build/bin/adapterCheck`. Use fresh output directories on a rerun. Both offline and public compatibility passed, each missing `turn-history.jsonl` negative rejected, and each actual recorded-only saved pass reported `missing_evidence=false`. Durable receipts and SHA-256 bindings are in `current-v2-proof-summary.json` and the paired `current-v2-*-receipt.json` files.

The current work is still partial. Implement selected executable Native construction and four-camera acquisition, physical-risk fallbacks, independent delivery and comparison audits, and the separate pedestrian and concurrent-indication duties. A diagnostic synthetic fixture does not establish original pixels, official signal governance, traffic lawfulness, cautiousness, physical completion or legal compliance.

The independent `current-v2-comparison-audit.py` passed on both retained exact sources and rejected a changed other-vehicle route at frame 205 with `Fixed comparison source differs: requested_other_xy_m`. It proves the requested arrow program and other route were held fixed while ego release changed; it does not establish actual lawful status. The audit receipt and hashed negative log are bound in `current-v2-proof-summary.json`.

## Selected controlled-case CPU milestone, 2026-11-24

Selected primary and fallback1 Native bundles for controlled_1 and controlled_2 pass four exact current-runtime offline checks. The prospective Native runner captures 600 synchronous frames, four cameras, actor history, requested flashing yellow signal state and restoration, while retaining signal governance and legal status as unverified. Four current-runtime public compatibility proofs pass Native validation, source analysis, Core conversion, Lean decoding, render and a missing turn-history negative. Both selected primaries pass actual recorded-only process-saved with missing_evidence=false. Receipts and SHA-256 bindings are in `selected-offline-proof.json`, `selected-compatibility-proof.json` and `selected-saved-*-processing.json`. The branch request source and comparison validation for pedestrian yield and concurrent indication are in `native/branch_scenarios.py`; six planned cases and three comparisons are in `case-plan.json`.

The package remains partial. The pedestrian and concurrent-indication branches need selected construction and public/saved proofs; semantic, physical-source, delivery and comparison audits and exact scoped strict gate remain. The existing controlled sources are synthetic CPU diagnostics, not physical or legal acceptance.

## Six-case selected offline milestone, 2026-11-24

`native/build_branches.py` materializes four additional pedestrian and concurrent-indication cases, each with primary and fallback1. `native/native_runner_branches.py` requests a crosswalk pedestrian for the two pedestrian cases and records the concurrent straight indication request for the other pair; `native/finalize_branches.py` reads retained 600-frame sources and leaves legal status, signal governance and cautiousness unknown. All eight new exact constructions pass current-runtime offline, for twelve selected primary/fallback1 offline passes total. `selected-branch-offline-proof.json` hashes the eight branch logs. `native/branch_scenarios.py` validates the two new one-intervention comparisons.

Four selected controlled-case public positive/missing-source-negative compatibility proofs and two controlled primary saved-only chains pass. The four branch public and saved chains, semantic, delivery and independent comparison audits remain in progress; no physical or legal acceptance is claimed.

## Corrected six-case branch proof checkpoint, 2026-11-24

The concurrent pair is a left turn in both cases, matching the frozen turn cell. Its sole intervention is whether a simultaneous left-turn indication is requested; the movement, ego release and other traffic are fixed. The pedestrian pair keeps the requested right-turn path fixed and changes ego release relative to crosswalk pedestrian occupancy. All twelve selected primary/fallback1 constructions pass exact current-runtime offline. All eight branch primary/fallback1 public compatibility runs pass positive analysis plus missing turn-history source negative; combined with controlled cases this is twelve public passes. All four branch primary saved-only process-saved chains pass with missing_evidence=false; combined with controlled cases this is six primary saved-only passes. Source-hashed receipts are selected-branch-offline-proof.json, selected-branch-compatibility-proof.json and selected-saved-*-processing.json. Independent branch comparison audit passes and rejects changed fixed route.

Status stays partial. The semantic cases stage, physical/lifecycle fixtures, delivery audits, final execution manifest and exact scoped strict gate remain CPU work. Synthetic fixtures do not establish actual arrow governance, pedestrian or traffic lawfulness, cautiousness, physical completion or legal compliance.

## Six-case physical/lifecycle fixture checkpoint, 2026-11-24

`native/prove_physical.py` executes source-shaped synthetic CPU fixtures for each selected primary: full 600-frame route progress, incomplete 150-frame source, missing source, and ordered ownership closure. `native/build_physical_proofs.py` ran all 24 fixtures and wrote source/hash-bound receipts under `physical/`. The pinned `physical_preparation.validate` passed for all six receipts. The 8 m progress check is an engineering fixture criterion only; all receipts explicitly say `synthetic_fixture` and `original_native_motion_verified=false`. Physical completion and legal judgment await original Native capture and independent review.

## Six-case delivery source audit checkpoint, 2026-11-24

`audit-selected-delivery.py` independently joins 600 retained trace, turn-history, video-frame and capture-evidence rows for every selected primary, verifies source hashes against public compatibility and saved-only receipts, checks the four camera source hashes and leaves physical/legal acceptance false. Each case passes the positive fixture and rejects removal of `turn-history.jsonl`; `selected-delivery-proof.json` binds all twelve logs. These are synthetic diagnostic source checks. Original pixels, signal governance, participant lawfulness, cautiousness and physical completion remain for local review.

## Current construction and semantic repair, 2026-11-24

The six selected cases and twelve primary/fallback1 constructions were rebuilt after fixing strict-ready capture coverage. Root and inline configurations now list all six selected case IDs and give each of the four full-profile cameras a pose strategy. `case-plan.json` supplies the exact 30-second synchronized camera plan. The eleven frozen mandatory source-observation terms now have source-reference recording channels in every selected construction; their per-frame records point to original turn history and four camera sources, state `original_source_review_pending`, and carry null legal classification. The root source mapping names all eleven terms and bound channel references. No official signal governance, lawful status, cautiousness or original Native capture is inferred.

The canonical semantic delivery validates all ten stages and all six selected case recording descriptions (semantic-index SHA-256 `b639b942451b2b19091a4c98653df7e5d1db38949b609abca6986fabd07c4107`). The focused root checks pass the eleven-term mapping, six-case configuration, four camera poses and twelve current construction hashes. Six physical preparation fixture receipts were regenerated and independently validate against the new construction hashes. Earlier offline, public and saved receipts are superseded by this rebuild; `result.json` remains partial while all selected proofs are rerun. Controlled_1 current-runtime public compatibility smoke passed with the new source-reference channels, including the missing-turn-history rejection and Core/video checks.

## Strict root contract repair, 2026-11-24

The first exact scoped strict gate reached the root construction and rejected missing `static_checks` at `preparation.py:195`; `termination_rules` was also absent. Status was immediately restored to partial. `native/build_selected.py` now supplies both source-faithful fields to every selected primary/fallback construction. The static checks require exact identity, 600 synchronized frames, four original camera sources, source-joined motion/signal requests and explicit unresolved legal review. Termination requires full capture and encoder closure or explicit failure with world restoration. All twelve construction hashes and six physical fixture receipts were regenerated. The earlier final manifest and CPU receipts are superseded; a fresh full exact-case offline/public/saved matrix is running before the next strict attempt.
