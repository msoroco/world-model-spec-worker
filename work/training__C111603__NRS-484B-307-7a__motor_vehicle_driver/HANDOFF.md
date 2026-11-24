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
