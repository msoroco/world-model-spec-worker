# CPU preparation checkpoint — 2026-11-15

Goal remains active. `.venv-cpu/bin/python runtime.py preflight` passed after the environment update with pinned CPU packages, ffmpeg/ffprobe, and Lean/Lake 4.28.0. The earlier missing-package, package-index, and missing-tool diagnoses are closed. No frozen inputs, runtime files, or `batch.json` were edited; no Git command was run.

The latest full strict gate (`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`, output `strict-batch-gate.log`) traversed the current returned work and failed at `preparation.py:276`: `Preparation acceptance failed: partial/missing packages remain`. Current result inventory: 3 ready, 40 partial, 0 missing. This is unfinished worker-owned CPU preparation, not an external blocker. Return-file count was brought below the 8,600 cap by moving 94 generated `work/**/__pycache__` directories to ignored `.runtime-work/retired-pycache/20261115/`; recheck the count before the next full gate because new test runs recreate caches.

Recent construction and exact proof progress:

- C149237 heavy-truck 120 m conditions-permitting sweep point: staged source-hashed primary and three distinct camera fallbacks now pass exact offline, positive/missing-source negative compatibility, recorded-only saved processing, and pinned four-plan fallback validation. `sweep-stage-manifest.json`, `sweep-stage-proof.log`, and that assignment's `HANDOFF.md` have the exact evidence. Scoped `--complete` passes. Keep partial: the point is staged outside the canonical eleven cases; the remaining sweep points and their fallback/proof chains, physical/delivery/comparison contracts, and source-backed feasibility review remain to build. Native motion, realized truck dimensions, camera visibility, and legal conditions-permitting judgment remain unverified.
- C10301 80 mph speed review: three exact selected cases each have primary plus three fallbacks with offline, compatibility, and saved-processing proofs. Independent fixed-condition comparison accepts unchanged controls and rejects a modified camera. Its measured synthetic peaks are 0.12369 mph in all three cases, so measured 80 mph boundary coverage is false. Scoped `--complete` passes. Keep partial; see its `HANDOFF.md` for the remaining physical, public-way authority, and delivery work.
- C215286 crosswalk: both selected cases now have primary plus three distinct, exactly proved fallbacks and pass pinned four-plan validation and scoped `--complete`. Keep partial; reviewed real site sources, semantic chain, physical-preparation proof, and full-duration delivery audit remain. See its `HANDOFF.md`.
- C125745 stop sign: first selected exact case now has primary plus three distinct fallback constructions; all pass exact offline, positive/negative compatibility and recorded-only saved processing. Twenty-nine CPU tests and scoped nonstrict check pass. The other three selected cases and their fallback constructions/proofs, canonical proposals, comparison/delivery and physical-preparation receipts remain. See its `HANDOFF.md` for ongoing partition-owner work.

Next CPU actions: finish the other three C125745 cases and fallbacks; select and prove all C149237 sweep points canonically; then continue remaining partial assignments one at a time through scoped strict checks. Build the shared full-batch branch matrix, ordered queue, and local integration evidence when package constructions exist. Re-run the complete strict gate after each truthful readiness change. Mark an assignment ready only after its own CPU proofs and scoped strict gate pass. The independent timer owns commits and pushes.

The settled-tree rerun of the full strict gate after all four current partition updates again reached `preparation.py:276` and failed only on `partial/missing packages remain`; `strict-batch-gate.log` is the latest output. At this checkpoint 3 assignments are ready and 40 remain partial. The active Goal is not complete.

## CPU continuation, 2026-11-15 (current Goal remains active)

Pinned `.venv-cpu` preflight, FFmpeg/ffprobe and Lean/Lake 4.28.0 were rerun successfully after the environment refresh. `worker_check.py --updates` reported no pause. The latest inventory before this continuation was 3 ready and 40 partial assignments. No frozen input, runtime, batch or Git operation was changed.

Partition 01 C149237 now selects 13 exact cases: the earlier 11 plus 120 m and 200 m conditions-permitting engineering-gap points. All eight new primary/fallback plans passed canonical exact offline, positive/negative compatibility and recorded-only saved processing (`canonical-sweep-proof.log`); new physical-classifier/lifecycle and independent delivery-audit fixtures passed (`canonical-sweep-physical-proof.log`, `canonical-sweep-delivery-proof.log`). The saved-source 120/152.4/200 m comparison checks original truck body vertices, fixed widths/blueprints/road/lane/cameras/duration/atoms, and missing-source/tampered-width rejection (`qualitative-sweep-comparison.log`). Pinned execution-manifest, semantic, physical and delivery contract validators pass all 13 (`contract-validation-sweep-v1.log`). Assignment `--complete` passes; scoped strict remains partial at `preparation.py:276`. The sweep specification is still incomplete because physical range feasibility and conditions-permitting judgment need original Native/source review. The synthetic evidence makes no Native or legal claim. Its assignment HANDOFF and result are updated.

Partition 02 C136559 has exact posted-below, posted-at, posted-above and outside-zone primaries passing offline, compatibility and saved processing; fallbacks and remaining contracts are underway. Partition 03 C125745 has all four selected exact cases with primary plus three fallbacks (16 plans), each passing offline, positive/negative compatibility and saved processing; comparison compatibility passes, while semantic/physical/full-frame delivery contracts remain. Partition 04 C147311 has two selected cases and six fallbacks passing exact offline/compatibility/saved; a five-stage semantic chain and route/camera CPU checks pass. Its owner is repairing a short-route physical-completion target and rebinding proofs, so the full gate should run after that manifest settles. All three results remain partial; consult each assignment HANDOFF for current commands and receipts.

To preserve the 8,600 returned-file cap, 77 unreferenced historical C125763 ready-package logs were moved to ignored `.runtime-work/retired-logs/partition01-20261115-wave5/paths.json`. The current strict scoped ready check for that package still passes. The returned `work/` file count after archive and ongoing agent edits was 8,528. Continue retiring only unbound historical logs as needed; do not remove current proof references.

The next root actions are to rerun settled assignment checks and the full strict gate, then continue constructing the next partial partition 01 assignment (C109749 staged signal-distance cases are prepared for canonical selection and fresh proofs). The shared ordered delivery queue and tested canonical local integration are still missing worker-owned CPU deliverables. Do not label those as external blockers or mark partial packages ready. Update this handoff with the next full gate result before ending a turn.

An additional 71 unreferenced historical logs from ready C125697 were retired to ignored `.runtime-work/retired-logs/partition01-20261115-wave6/paths.json` for file-cap headroom. The package's scoped strict ready gate still passes after this archive. Historical HANDOFF mentions are archival, and current proof-bound logs were retained.

The first complete-batch strict rerun after C147311 settled exited 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). It passed the return-file cap and all preceding static checks. C136559 and C125745 then completed additional stable CPU checkpoint bindings; run the full gate again after later partition edits settle. C136559 has 4 selected cases x 4 exact constructions with offline/compatibility/saved proofs and a validated five-stage semantic chain; its independent source audit rejects changed sign context but no positive physical delivery claim is made. C125745 has a validated nine-stage semantic chain, four 900-frame synthetic saved attempts, independent timing comparisons, four physical-preparation receipts and prospective delivery contracts. Both scoped `--complete` gates pass; both remain partial for their exact original-source and physical acceptance gaps. Partition 04 C147311 is stable with its repaired 12 m route-progress criterion, eight exact reproofs and pinned physical/delivery contracts. Its owner has begun C109705 centerline construction review. Partition 03 has begun C331230 crosswalk-first construction.

Ten unbound historical C125745 logs were retired to ignored `.runtime-work/retired-logs/partition01-20261115-wave8/paths.json` for file-cap headroom; its scoped nonstrict check still passes. The earlier archive of one unbound C125714 ready-package log is in `partition01-20261115-wave7/paths.json`; ready-package strict status was not changed by any current proof edit.

## Latest strict gate and partition checkpoint, 2026-11-15

After the C136559/C125745 stable bindings and C109749 semantic-target edit, `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` was rerun. `work/_shared/strict-batch-gate.log` records exit 1 at `preparation.py:276`, exactly `Preparation acceptance failed: partial/missing packages remain`. All preceding return-file and static checks passed. The current pinned returned-file count after subsequent C331230 additions is 8,583 of 8,600, excluding bytecode/cache; avoid adding more than 17 returned files before archiving or compacting historical unbound evidence.

Partition 01 C109749 now has `signal_target_m` in the canonical template, binding and all 13 existing proposal cases as a 30.48 m authored controller target; `validate_semantic_signal_target.py` passes the pinned eight-stage/12-selected-case semantic chain and the scoped assignment check passes. An isolated, reverted semantic probe validated the planned 25 m and 36 m staged cases against a 14-case in-memory selection. They are not yet canonically selected, so exact canonical reproof and physical/delivery/comparison bindings remain worker-owned CPU work. C149237 remains partial with the 13-case sweep proof and unresolved physical judgment as described above.

Partition 03 C331230 now has a first exact marked-crosswalk construction and offline/saved-source halt-ordering proof, including missing-history rejection. Scoped `--complete` passes. Its unreviewed synthetic site, remaining cases/fallbacks, compatibility and delivery work remain; its assignment HANDOFF has the current construction hash. Partition 04 C109705 has source-reviewed near/far left-turn route planning and bounded controller CPU tests; integrated runner and exact constructions remain. Both results are partial. The Goal is still active; no ready status was promoted and no frozen input, runtime, batch file or Git operation was changed.

Partition 04 C109705 then completed its first exact marked near-centerline construction with a CARLA-lazy four-camera runner. `exact-offline.log` and five CPU tests pass; its scoped `--complete` check passes after result/HANDOFF binding. Remaining three cases, fallbacks, compatibility/saved and Native/source review are unfinished. Its result remains partial.

Final settled-tree strict rerun after all partition owners completed their current checkpoints: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1, with the exact final error `Preparation acceptance failed: partial/missing packages remain` at `preparation.py:276` (`work/_shared/strict-batch-gate.log`). The cap and preceding static checks passed. Current result inventory is **3 ready / 40 partial**, all 43 present; returned `work/` count is 8,583 / 8,600. The next worker-owned CPU tasks include C109749 staged signal-case canonical selection/reproof, C136559 physical/delivery contract completion, C125745 original-source and delivery work, C331230 other crosswalk cases/fallbacks, C109705 remaining exact constructions and proofs, and the shared ordered queue/local integration. Preserve partial statuses until each scoped strict gate passes. The active Goal is not complete.

## Current turn: canonical C109749 signal-distance proofs, 2026-11-15

The 25 m and 36 m signal-onset cases are now selected in C109749's canonical manifests (14 selected cases). Both cases have four exact canonical offline, compatibility with missing-history rejection, and recorded-only saved-processing paths; the new source-measurement validator confirms eight paths and no legal or physical acceptance claim. Bound existing physical and delivery fixture contracts, reran eight-stage semantic validation, and passed the scoped complete check. C109749 remains partial for other worker-owned grids and Native/source/legal judgment. To create headroom below the 8,600 returned-file cap, 65 unreferenced historical logs from C125751, C149237 and C125745 were archived under ignored `.runtime-work/retired-logs/20261115-cap-headroom/`; the archived path list is `paths.json` there. All three affected scoped complete checks passed after the move. No frozen input, runtime, batch.json or Git action was changed.

The settled-tree full strict gate was rerun after the C109749 promotion: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). All preceding structural checks passed. Inventory remains 3 ready / 40 partial across 43 packages; returned `work/` file count is 8,569 / 8,600. The active Goal remains open. Next worker-owned work includes C109749 remaining signal/yield/hazard grids; C136559 positive physical and delivery acceptance; C125745 original-source and pixel provenance; C331230 remaining crosswalk cases/fallbacks; C109705 remaining constructions and compatibility/saved proofs; shared ordered queue/local integration. Do not mark these ready before their CPU proof requirements pass.

## Current continuation: C331230 no-crosswalk alternatives, 2026-11-15

Reran `worker_check.py --updates` (version 0, no pauses) and `runtime.py preflight` (Python CPU, Lean 4.28.0, no simulation). An independent read of NRS 484A.450(2) exposed missing no-crosswalk stop-line and no-crosswalk/no-line sight-reference alternatives in C331230's plan. Added both exact case IDs and controlled comparisons, and implemented source-bound original-frame measurement code with six passing CPU tests, including missing/stale/inconsistent sight-source rejection. The scoped complete check passes; C331230 remains partial because those and the earlier cases still need exact constructions, fallbacks, compatibility/saved proofs, semantic and independent delivery/comparison audits. This is unfinished worker-owned CPU work, not an external blocker. No frozen input, runtime, batch.json or Git operation was changed.

Settled-tree strict rerun after this C331230 change: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). This is the current strict verdict; the 43 package results remain 3 ready / 40 partial. Returned `work/` count is 8,572 / 8,600. Continue the Goal with the exact CPU construction and proof actions above; do not promote partial results on this checkpoint.

C331230 additionally gained `stop_reference_finalizer.py` and eight passing CPU tests for the stop-line and sight alternatives. The finalizer binds original source hashes and preserves legal/physical uncertainty. The tiny fixture camera placeholders were not decoder proofs; exact compatibility and process-saved remain next CPU actions. Status stays partial.

Final settled-tree strict rerun after C331230 saved-finalizer work: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). Structural checks ahead of that status requirement passed. Inventory remains 3 ready / 40 partial across all 43 assignments; returned `work/` count is 8,574 / 8,600. Goal remains active. Next C331230 work is exact constructions and source-backed fixture recipes for `__no_crosswalk_marked_stop_line` and `__no_crosswalk_no_line_first_view`, each with fallbacks and canonical offline, compatibility, process-saved and audits; the earlier four cases also need those proofs. Actual Native sign/marking/sight provenance and physical/legal judgments remain unverified separately.

## Current continuation: C331230 exact stop-line bundle, 2026-11-15

Pinned preflight passes with Python CPU and Lean 4.28.0; updates remain version 0 with no pauses. C331230 now has a second exact selected construction, `__no_crosswalk_marked_stop_line`, with a separate source-bound runner/finalizer and two materialized offline CPU checks. Its current construction SHA and exact offline command are in the assignment HANDOFF; scoped `worker_check.py --complete --assignment testing__C331230__NRS-484A-450-2__motor_vehicle_driver` passes. A four-camera textual diagnostic recipe and selected measurement contract were added. The compatibility attempt reached the pinned converter and stopped at missing synthetic Native-shaped `capture/native/frames.jsonl` and graphs (`stop-line-compatibility-attempt.log`); constructing those case-consistent sources and rerunning compatibility/process-saved are worker-owned next actions. The result remains partial, as do the other incomplete assignments. No frozen input, runtime, batch.json or Git operation was changed.

Settled-tree full strict gate rerun after this construction: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). The full inventory remains 3 ready / 40 partial across 43 packages, and returned `work/` count is 8,586 / 8,600. C331230's scoped complete check passed but its exact compatibility/source graph and other CPU deliverables remain, so the Goal stays active.

C331230 next-case checkpoint, 2026-11-15: the exact no-crosswalk/no-line first-view construction, four-camera textual fixture, measurement contract, offline proof and positive/negative saved-only analysis are now present. C331230 remains partial because exact compatibility still lacks a case-consistent Native frame/graph packet, and other selected cases/fallbacks/semantic/delivery/comparison proofs remain worker-owned. The marked-line construction was rebuilt after the shared finalizer changed and its offline proof rerun. CPU preflight passes with the pinned environment; the eight C331230 tests and scoped complete check pass. The first-view compatibility traceback is retained in `work/testing__C331230__NRS-484A-450-2__motor_vehicle_driver/first-view-compatibility-attempt.log`. Current inventory before the final strict rerun: 3 ready / 40 partial, 8,598 returned work files. No frozen input, runtime, batch or Git action was changed.

Final strict batch rerun after the first-view runner correction and scoped recheck: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain`; `strict-batch-gate.log` retains the exact traceback. Inventory remains 3 ready / 40 partial across 43 reported assignments, and returned work has 8,598 files of the 8,600 cap. C331230 is partial; its latest exact first-view offline proof passed at `.runtime-work/c331230-first-view-offline-v4`, and the latest compatibility attempt still lacks `capture/native/frames.jsonl`. Continue the worker-owned Native-shaped frame/graph packet and remaining branch/fallback construction; do not promote status yet.

## Current five-case C331230 checkpoint

C331230 now has five exact selected constructions with passing offline, synthetic diagnostic compatibility (including negative source removal), and recorded-only saved processing. The new crosswalk-plus-marked-line precedence case selects the crosswalk with the line present; exact commands, construction hashes and receipt paths are in the assignment `HANDOFF.md` and `result.json`. Scoped complete check passes; the result remains partial because the unmarked-crosswalk case, fallbacks, canonical semantic stages and independent audits are unfinished worker-owned CPU work. Earlier missing CPU dependencies and Native-shaped synthetic frame packets are no longer blockers. The Goal remains active.

Final strict rerun after the five-case C331230 proofs exited 1 at `runtime/scenario_pipeline/worker_exchange/preparation.py:276`: `Preparation acceptance failed: partial/missing packages remain`. Inventory is 3 ready and 40 partial of 43 results. C331230 scoped `--complete` passes, while its status remains partial. A subsequent C331230 independent crosswalk-priority comparison and ten-test suite also pass and are bound in `result.json`. Returned `rg --files work` count is 8,599 of 8,600. Current environment preflight passed; no frozen input, runtime, batch.json or Git operation was changed. Continue the worker-owned unmarked-crosswalk construction and other missing CPU deliverables.

C331230 later added the sixth selected unmarked near-side crosswalk bundle. Its exact offline, synthetic compatibility with negative source removal, and recorded-only processing pass, bound in `result.json`; scoped complete passes. All six primaries now have those CPU proof classes. This remains partial: fallback constructions, semantic stages and independent delivery/comparison audits are still worker-owned, and Native sidewalk geometry is unreviewed.

The unmarked case Native waypoint-check implementation received an additional fake-map CPU test. Eleven C331230 tests pass; its exact construction, compatibility and saved proofs were rerun and bound at the latest hashes in assignment `result.json`. C331230 remains partial.

C331230 marked-versus-unmarked source comparison is now implemented and its positive/negative CPU test passes. Twelve assignment tests and three source comparisons are bound. Scoped complete still passes; C331230 remains partial pending worker-owned fallbacks, semantic proposals, delivery audits and remaining comparisons.

Final settled-tree strict gate after the six-case C331230 construction and twelve tests exited 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`; `work/_shared/strict-batch-gate.log` retains the traceback. All earlier static/returned-file checks passed. Current inventory remains 3 ready / 40 partial of 43; C331230 is partial, and its scoped complete check passes. Returned `rg --files work` count is 8,587 / 8,600 after archiving 24 zero-byte, unbound historical C101303 analysis logs to ignored `.runtime-work/retired-logs/c101303-zero-byte-analysis/`. No proof-bound receipt was removed. Continue worker-owned CPU preparation rather than treating this as an external blocker.

C331230 continuation: the marked-before case now has three distinct exact fallback constructions, each passing offline, positive/negative compatibility and recorded-only saved processing. Their candidate invariants and all proof hashes are bound in its manifest; all six primaries now have post-capture command/receipt/feedback bindings. Fifteen C331230 fallbacks and other CPU deliverables remain worker-owned; no ready status was promoted. Zero-byte unbound C101303 historical analysis logs were archived to ignored `.runtime-work/retired-logs/c101303-zero-byte-analysis/` to preserve the returned-file cap.

C331230 continuation added three fully CPU-proven fallbacks for each of the two marked-crosswalk selected cases (six total), plus recorded-only post-capture bindings for all six primaries. Candidate invariant/proof validation and scoped complete checks pass; twelve C331230 fallbacks remain across four cases. The earlier archived C101303 manifest-bound zero-byte logs were restored after detecting the reference; C101303 scoped complete passes. Only 48 path-unreferenced zero-byte logs across C109749, C129731 and C101303 were then archived to ignored `.runtime-work/retired-logs/unreferenced-zero-byte/`; all three affected scoped complete checks pass. Returned file count is 8,599 / 8,600, requiring further careful consolidation before adding receipt files. No frozen input, runtime, batch.json or Git action was changed.

Final strict rerun after six C331230 fallbacks and log restoration exited 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`; exact traceback retained in `work/_shared/strict-batch-gate.log`. All earlier full-batch static and returned-file checks passed, confirming the safe cleanup did not break referenced proofs. Inventory remains 3 ready / 40 partial of 43. The Goal remains active; the failure is unfinished CPU preparation, not an external dependency.

## Current continuation: three no-crosswalk marked-line fallbacks, 2026-11-15

Constructed three distinct exact fallbacks for `__no_crosswalk_marked_stop_line`: a longer brake hold, repositioned reference-corner camera, and earlier ego spawn. Each has a predeclared measurable trigger and distinct changed knob. Exact offline, positive/negative source-bound synthetic compatibility, and recorded-only process-saved commands passed; commands, receipt hashes, construction hashes, and source logs are bound in `execution-manifest.json` and `result.json`. `candidate_constructions.validate(... required=True, require_alternate=True, candidate_count=4)` passes for this exact case, as does its scoped `worker_check.py --complete`. These are CPU/software proofs; physical and legal acceptance remain unclaimed. C331230 remains partial.

To stay within the 8,600 returned-file cap, 12 JSON-unreferenced historical C125745 check logs and six JSON-unreferenced historical C125763 check logs were moved byte-for-byte to ignored `.runtime-work/retired-logs/c125745-historical-checks/` and `.runtime-work/retired-logs/c125763-historical-checks/`. Scoped complete checks for both packages passed after relocation. `rg --files work` is 8,599 / 8,600. The next worker-owned CPU work is three fallbacks each for `__no_crosswalk_no_line_first_view`, `__crosswalk_and_stop_line`, and `__unmarked_crosswalk_stop_before`, then canonical semantic stages and independent delivery/comparison audits. Do not mark ready until the full CPU proofs pass. No frozen input, runtime, batch.json, or Git action was changed.

Settled-tree strict gate after all three no-crosswalk marked-line fallbacks: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). All preceding static checks passed. Inventory remains 3 ready / 40 partial across 43 packages, with C331230 partial. The active Goal remains open; nine C331230 fallbacks and its remaining CPU semantic and delivery audits are worker-owned next actions.

## Preserved historical check logs for returned-file headroom

The following JSON-unreferenced historical check logs were relocated byte-for-byte to ignored `.runtime-work/retired-logs/20261115-next-fallback-headroom/`. Their original contents are copied below to preserve the checkpoint in returned text.

### testing__C125745__NRS-484B-250-1__motor_vehicle_driver/assignment-check.log (SHA256 d93b38cacbdeca49ad9a3e094ead5aef404b609da98114fb90f6a6a130d47d4b)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125745__NRS-484B-250-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125745__NRS-484B-250-1__motor_vehicle_driver/strict-gate.log (SHA256 d6960eedad188c5a7f944fde31c4339a6bb7eab414f6d284219a56d71d5e3be1)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C125763__NRS-484B-250-1__motor_vehicle_driver

```

### testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/assignment-check.log (SHA256 98c71956a44f4c788ad55d328ac92810cb0355b02eba461cbfd608c8ed493f59)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158196__NRS-484B-307-6a__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/strict-gate.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C158190__NRS-484B-257-2__motor_vehicle_driver/assignment-check.log (SHA256 950a4770b5e672f331818e1ec0996dcf70d83b08e461fa7f59a9e52b7f303095)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158190__NRS-484B-257-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158190__NRS-484B-257-2__motor_vehicle_driver/strict-gate.log (SHA256 9bc598a1adc03d8a2d41ba90ba845b8f17bd1d8cd770fc093122384de61c6d59)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C158208__NRS-484B-257-1__motor_vehicle_driver

```

### testing__C24757__NRS-484B-250-4__motor_vehicle_driver/assignment-check.log (SHA256 23368e1acdea79d1481365bc24ac91c7a7292759cb9338a032c3105b03cf9d62)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C24757__NRS-484B-250-4__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C24757__NRS-484B-250-4__motor_vehicle_driver/strict-gate.log (SHA256 20fc34d2dd9fb03692468a5971efb01cea07a7eca10b30147d0ffa54b591735f)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C378304__NRS-484B-413-2__motor_vehicle_driver

```

### testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/assignment-check.log (SHA256 18170831ee9eab01c13d2d9091ffbdb254b9bd3de6a07cac6c1b4138f21ed482)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C109705__NRS-484B-400-2b__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/strict-gate.log (SHA256 c28611b6994597918e32cf84532ccecc25724243a47bbe7f97f341f9b4c568c7)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C125714__NRS-484B-250-1__motor_vehicle_driver

```

### testing__C157964__NRS-484B-257-2__motor_vehicle_driver/assignment-check.log (SHA256 941ea1aaf9e3241e52fbe0147789ad47f414d21a4468c627711a4b6893acf8ba)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C157964__NRS-484B-257-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C157964__NRS-484B-257-2__motor_vehicle_driver/strict-gate.log (SHA256 f0721b9f5af022a93e1e52ed46dc31e62e9abd3aab22659ad886aadf033ea771)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C158196__NRS-484B-257-2__motor_vehicle_driver

```

### testing__C10301__NRS-484B-600-1e__motor_vehicle_driver/assignment-check.log (SHA256 1a22cfbe833b96d2e951c9c0c95975b8b7ba115583ac737204bda43bfc0bd282)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C10301__NRS-484B-600-1e__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C10301__NRS-484B-600-1e__motor_vehicle_driver/strict-gate.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C80909__NRS-484B-227-1__motor_vehicle_driver/assignment-check.log (SHA256 d2173e0a136c6739486bcea18071bbc865f00c2b1f6e5b1ab77d4f03139e4045)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C80909__NRS-484B-227-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C80909__NRS-484B-227-1__motor_vehicle_driver/strict-gate.log (SHA256 0a22e5b309653736241810f97f1de989fffff571fcd0f9799c1a3f9e2492de59)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C109705__NRS-484B-400-2b__motor_vehicle_driver

```

### testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/assignment-check.log (SHA256 57fe17688791f3d201a2f3c07c780865aec8de7a4a688b277a172a99717a8be0)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/strict-gate.log (SHA256 755f5767e178dfd1f638139556ce98cef4bf9ec8e3178de113f5bdbb88acbd0b)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C125697__NRS-484B-250-2__motor_vehicle_driver

```

### testing__C158208__NRS-484B-257-1__motor_vehicle_driver/assignment-check.log (SHA256 b872068c65461868521dd6530ae9acf3ceb949cc861fb8e397897e1e49ce8e81)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158208__NRS-484B-257-1__motor_vehicle_driver/strict-gate.log (SHA256 6f6e9ecda590bf19e062cb38181a56ae63ba212a9c915e487cfc690c01263c06)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C178244__NRS-484B-413-2__motor_vehicle_driver

```

## Preserved historical check logs for crosswalk-line fallbacks

These JSON-unreferenced historical logs were relocated byte-for-byte to ignored `.runtime-work/retired-logs/20261115-crossline-fallback-headroom/`. Exact text is preserved here.

### testing__C412593__NRS-484B-413-2__motor_vehicle_driver/assignment-check.log (SHA256 0be0bc31870ad921bb251420882b6aa36c6e3eff0bba4e53212675131f8d9a72)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C412593__NRS-484B-413-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C412593__NRS-484B-413-2__motor_vehicle_driver/strict-gate.log (SHA256 6fbf270990698fb82cf4fbc454676ea7ec6f51b9721349ac58a0289eb10140f3)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C109705__NRS-484B-400-2a__motor_vehicle_driver

```

### testing__C215286__NRS-484B-113-2__motor_vehicle_driver/assignment-check.log (SHA256 6648ac6f7d4496e84968d2e2741ae6750a0be6fa3f92bf0a5af3927f21b1724a)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C215286__NRS-484B-113-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C215286__NRS-484B-113-2__motor_vehicle_driver/strict-gate.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C378304__NRS-484B-413-2__motor_vehicle_driver/assignment-check.log (SHA256 68222bc4547631ef425a8135f179e8cd14335ce81fa041fa614eae511e79d38f)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C378304__NRS-484B-413-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C378304__NRS-484B-413-2__motor_vehicle_driver/strict-gate.log (SHA256 3ec560e66986fe34df9f29f0358457169324550f45ed274e32806cf605d1ce13)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C10301__NRS-484B-600-1e__motor_vehicle_driver

```

### testing__C144550__NRS-484B-223-1b__motor_vehicle_driver/assignment-check.log (SHA256 730d7a22fe4a4c84ed7acea83c697fedd9d657f0ef0a9c8496949ad412f94a31)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C144550__NRS-484B-223-1b__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C144550__NRS-484B-223-1b__motor_vehicle_driver/strict-gate.log (SHA256 50a556927021de513a94e1a24b69e7345fe5094ec10f9490171ee3b98b1dfc63)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C157964__NRS-484B-257-1__motor_vehicle_driver

```

### testing__C126120__NRS-484B-227-1__motor_vehicle_driver/assignment-check.log (SHA256 d5d5be0dd2c12f71ba3b3ce08ce5652c5d30583ee515e772621460e6aaee73ef)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C126120__NRS-484B-227-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C126120__NRS-484B-227-1__motor_vehicle_driver/strict-gate.log (SHA256 2d0caeae5c4d6cac911dd892acf77441c5801042d21311a335195381d362a344)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C147311__NRS-484B-220-1__motor_vehicle_driver

```

### testing__C158196__NRS-484B-257-1__motor_vehicle_driver/assignment-check.log (SHA256 0a0f97d22284a9bb0013d70628066b3118e31f46b4f9ace51d67966a92558f81)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158196__NRS-484B-257-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158196__NRS-484B-257-1__motor_vehicle_driver/strict-gate.log (SHA256 c8948a239209298c18834119004ee832dbebfeffa1b5e380a9415d2f4d164989)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C158208__NRS-484B-257-2__motor_vehicle_driver

```

### testing__C157964__NRS-484B-257-1__motor_vehicle_driver/assignment-check.log (SHA256 1adf2508bd2d5954df70a1f7a373521941162ed66477e9f4ed87a3591edd0c33)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C157964__NRS-484B-257-1__motor_vehicle_driver/strict-gate.log (SHA256 74e65b1bf9d7f2ce9bcf79a3d7c52d9c422138c4f6af641e0c3df22a50d050ca)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C158196__NRS-484B-257-1__motor_vehicle_driver

```

### testing__C24811__NRS-484B-250-4__motor_vehicle_driver/assignment-check.log (SHA256 22e6006f669fee7cf2bffb8f7920743b284a2b3c39e2e6f116c3d64c4c0df4d9)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C24811__NRS-484B-250-4__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C24811__NRS-484B-250-4__motor_vehicle_driver/strict-gate.log (SHA256 a4ced8867e19a1b3dac4be368d44443c7f3d438f0a89732f7a11655f56c31208)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C412593__NRS-484B-413-2__motor_vehicle_driver

```

### testing__C178244__NRS-484B-413-2__motor_vehicle_driver/assignment-check.log (SHA256 50defc2267b706e0968da187a80133378c24d6c5fe6324d788511b4a1c8c6768)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C178244__NRS-484B-413-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C178244__NRS-484B-413-2__motor_vehicle_driver/strict-gate.log (SHA256 e3a669bacbd61a9c0f29cfde8ef86cb7fd60bbb014f2caf93455cee88d13ff75)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C24811__NRS-484B-250-4__motor_vehicle_driver

```

### testing__C160013__NRS-484B-127-3__motor_vehicle_driver/assignment-check.log (SHA256 e8926cc1953b1f17f554dd4827d29b4875c274562f07e9692078704b0af9004c)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C160013__NRS-484B-127-3__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C160013__NRS-484B-127-3__motor_vehicle_driver/strict-gate.log (SHA256 ded502bb0f4128678fe48012626172f1da705b170505dd7fd3af790a542de844)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C215286__NRS-484B-113-2__motor_vehicle_driver

```

## Preserved historical check logs for unmarked-crosswalk fallbacks

These JSON-unreferenced historical logs were relocated byte-for-byte to ignored `.runtime-work/retired-logs/20261115-unmarked-fallback-headroom/`. Exact text is preserved here.

### testing__C149752__NRS-484B-127-2__heavy_vehicle_driver/assignment-check.log (SHA256 dc0b29990e6cb1afedd715cc76e5171ea9cfc2842456d878e412f5c417818de0)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C149752__NRS-484B-127-2__heavy_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C149752__NRS-484B-127-2__heavy_vehicle_driver/strict-gate.log (SHA256 e243ec675910a65a019992295e1c1b2cae94a75e28be8e8435ec7166079daccf)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C158190__NRS-484B-257-2__motor_vehicle_driver

```

### testing__C125697__NRS-484B-250-1__motor_vehicle_driver/assignment-check.log (SHA256 a3c935bb1d86b6d8cd0eead99fb7485b8e5cac77d3cbf0923bdce4b37e2c49c4)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125697__NRS-484B-250-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125697__NRS-484B-250-1__motor_vehicle_driver/strict-gate.log (SHA256 5c33a1acbe3e88efcc744ddda4c9886f95e1858d2dc8234c7e48025e92cfab4c)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C125745__NRS-484B-250-1__motor_vehicle_driver

```

### testing__C158208__NRS-484B-257-2__motor_vehicle_driver/assignment-check.log (SHA256 11c80a1a34c51fb5122e5e3049639f7d6f3d0af20e4d97031e6ec1bb79d87ea4)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158208__NRS-484B-257-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158208__NRS-484B-257-2__motor_vehicle_driver/strict-gate.log (SHA256 4a50bce5c2ea041394b7f58c658d9867dc43697781afdae564dd6da22228fce9)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C179789__NRS-484B-600-1a__motor_vehicle_driver

```

### testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/assignment-check.log (SHA256 993053d68f0844b1922d373bb8982ba3b894fde8a970ce53c6cd8f8d0b9a81b2)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C179789__NRS-484B-600-1a__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/strict-gate.log (SHA256 b718a54606a92a33a1d461bf11378785a74487d9554645ab5585fc20ca10f4aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C331230__NRS-484A-450-2__motor_vehicle_driver

```

### testing__C125763__NRS-484B-250-1__motor_vehicle_driver/assignment-check.log (SHA256 fb75743f059e3dfa55f26795d41afb31ebae4404d55262f31e0fa691fa050d1c)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125763__NRS-484B-250-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125763__NRS-484B-250-1__motor_vehicle_driver/strict-gate.log (SHA256 b355d3ca9e5574439dfdf2b694e1573674d4dcbaade40c2ad1294823b091739c)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C136559__NRS-484B-600-1c__motor_vehicle_driver

```

### testing__C177008__NRS-484B-413-2__motor_vehicle_driver/assignment-check.log (SHA256 a15f61b995b4a6e8c74aee3c780b80ffa13c903495638aeba728edc3a4272144)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C177008__NRS-484B-413-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C177008__NRS-484B-413-2__motor_vehicle_driver/strict-gate.log (SHA256 50172d9e09c57693844afae76563a143bfccf26da8e45d7b96d5193f35fea35f)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C24757__NRS-484B-250-4__motor_vehicle_driver

```

### testing__C376646__NRS-484B-250-4__motor_vehicle_driver/assignment-check.log (SHA256 4bb655dfb8ed845b2cc3f8d4fdd6e38f7375d8e94e0ef1bc97edcf55eff59db8)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C376646__NRS-484B-250-4__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C376646__NRS-484B-250-4__motor_vehicle_driver/strict-gate.log (SHA256 d4b85e02abadf9887c5d52bf3276202c8dd2b3055887744644a2e989a1a39674)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C125751__NRS-484B-250-1__motor_vehicle_driver/assignment-check.log (SHA256 c1a332d303fc8ec16e4b4328b67ecd05f22b40028839fb6423724cfa44434f16)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125751__NRS-484B-250-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125751__NRS-484B-250-1__motor_vehicle_driver/strict-gate.log (SHA256 bb96ff74630b5f8d11322db441dba04f8c1e99eb5ad530fe9d0f3703acf1a6b2)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C126120__NRS-484B-227-1__motor_vehicle_driver

```

## Preserved historical check logs for C331230 semantic work

These JSON-unreferenced historical logs were relocated byte-for-byte to ignored `.runtime-work/retired-logs/20261115-semantic-headroom/`. Exact text is preserved here.

### testing__C147311__NRS-484B-220-1__motor_vehicle_driver/assignment-check.log (SHA256 faaebed437d1791a2cd230cb9738e4b802d0906dc699e6cd5049e6d0b5dfb6b4)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C147311__NRS-484B-220-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C147311__NRS-484B-220-1__motor_vehicle_driver/strict-gate.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C158196__NRS-484B-257-2__motor_vehicle_driver/assignment-check.log (SHA256 5ca0416a5e6428387aa7bb3853255bc3beb6e811e6d8ad7c3f60c2fb3ba0b8c0)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C158196__NRS-484B-257-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C158196__NRS-484B-257-2__motor_vehicle_driver/strict-gate.log (SHA256 904c64c8d63f4a7a4b2f5314dd7d8c1d266df3ae3e7bc79a67efb7d2b42d6dc6)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 110, in check
    require(not complete, 'Missing result: '+aid)
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Missing result: testing__C160013__NRS-484B-127-3__motor_vehicle_driver

```

### testing__C125714__NRS-484B-250-1__motor_vehicle_driver/assignment-check.log (SHA256 6e94a17a997e5cf38119d23f3e464b6e26ff17ecd367104e5ecfee9f07c94d68)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125714__NRS-484B-250-1__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125714__NRS-484B-250-1__motor_vehicle_driver/strict-gate.log (SHA256 d4b85e02abadf9887c5d52bf3276202c8dd2b3055887744644a2e989a1a39674)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/strict-gate.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

### testing__C125714__NRS-484B-250-2__motor_vehicle_driver/assignment-check-current.log (SHA256 818de7401773c997c88df3058aa290716146eeba381d020530629d05e91a50f8)

```text
{
  "batch_id": "demo-test-delivery",
  "reported": [
    "testing__C125714__NRS-484B-250-2__motor_vehicle_driver"
  ],
  "static_checks_passed": true
}

```

### testing__C125697__NRS-484B-250-2__motor_vehicle_driver/strict-assignment-five-case-v1.log (SHA256 d4b85e02abadf9887c5d52bf3276202c8dd2b3055887744644a2e989a1a39674)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 22, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

## Current continuation: complete C331230 fallback set and semantic stage chain, 2026-11-15

All six selected C331230 cases now have three distinct physical-risk fallback constructions each (18 total). This turn completed `__no_crosswalk_no_line_first_view`, `__crosswalk_and_stop_line`, and `__unmarked_crosswalk_stop_before` with nine additional candidates. Each new candidate passed exact offline materialization, positive/negative source-bound synthetic compatibility, and recorded-only `process-saved`; exact commands, construction hashes and receipt hashes are in `execution-manifest.json` and `result.json`. `candidate_constructions.validate(... required=True, require_alternate=True, candidate_count=4)` passes for all six cases; scoped complete check passes. These proofs claim software compatibility only.

Added independent diagnostic comparisons for `halt_position` and `stop_line_hierarchy` in `stop_reference_comparison.py`, with positive source receipts, negative sign-ID tests and the 14-test C331230 CPU suite passing. The stop-line hierarchy check holds signed halt behavior and halt body location fixed while permitting the declared reference inventory change; a one-frame transit body position difference exists in the synthetic diagnostic packets, so no identical-full-trajectory claim is made. All five case-plan comparisons now have diagnostic source checks, plus one stop-line versus first-view diagnostic comparison. Independent Native delivery/comparison acceptance audits are still worker-owned.

Authored canonical relevance-batch, relevance, template, three judgment-observable, bindings, cases and semantic-index proposals under `proposals/`. The eight-stage `semantic_delivery.validate` passes for six selected cases and is recorded in `semantic-proof.log`; judgment sweep specs remain explicitly incomplete pending reviewed Native feasibility and coverage, so this does not make the package ready. The package remains partial. The next CPU tasks are independent delivery audit code and positive/negative fixture proofs for each selected case, complete feasible sweep proposals, exact statutory/branch review, then queue and shared integration bindings. Native physical/pixel/legal acceptance remains unclaimed.

To remain at the 8,600 returned-file limit, this turn relocated 66 JSON-unreferenced historical check logs to ignored `.runtime-work/retired-logs/`; their exact UTF-8 contents and SHA256 values are preserved in `work/_shared/HANDOFF.md`, and their original bytes remain in the archive. Every affected package's scoped complete check passed after relocation. No frozen input, runtime, batch.json or Git action was changed.

### testing__C125697__NRS-484B-250-2__motor_vehicle_driver/strict-assignment-semantic-v1.log (SHA256 8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa)

```text
Traceback (most recent call last):
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/worker_check.py", line 30, in <module>
    result = check(Path(__file__).resolve().parent, complete=args.complete or args.require_delivery_ready, require_ready=args.require_delivery_ready, assignment=args.assignment)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 276, in check
    require(len(results)==len(items) and all(r['status']=='ready' for r in results.values()), 'Preparation acceptance failed: partial/missing packages remain')
  File "/scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/runtime/scenario_pipeline/worker_exchange/preparation.py", line 10, in require
    raise ValueError(message)
ValueError: Preparation acceptance failed: partial/missing packages remain

```

The `sight_point_hierarchy` case-plan comparison now has a source-bound crosswalk-versus-first-view receipt (`sight-point-hierarchy-comparison.json`) and a negative missing-sight-history CPU test. All five planned comparisons have diagnostic source checks, plus the independent stop-line-versus-first-view check. The full C331230 suite reports 15 passing tests; scoped complete check and strict full-batch gate must be rerun after this latest edit.

Final settled-tree strict rerun after 18 C331230 fallbacks, six diagnostic comparisons and validated semantic stage chain exited 1 at `preparation.py:276`: `Preparation acceptance failed: partial/missing packages remain` (`work/_shared/strict-batch-gate.log`). All preceding static/returned-file checks passed. The inventory is 3 ready / 40 partial of 43; `work/` has exactly 8,600 files, and C331230 scoped `--complete` passes while its status remains partial. Goal remains active. Worker-owned next actions are independent delivery audit construction and positive/negative proofs for C331230, complete feasible judgment sweep plans and statutory review, followed by other incomplete assignments and shared queue/integration. No external dependency is asserted.
