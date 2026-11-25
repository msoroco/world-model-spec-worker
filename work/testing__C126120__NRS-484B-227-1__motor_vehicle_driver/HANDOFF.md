## 2026-11-25 fixture and semantic checkpoint

Both source-shaped synthetic fixture recipes materialize with `runtime.py fixture`, retaining logs under each case. The canonical stage builder now produces draft relevance, template, binding and cases proposals. `validate_semantic_proposals.py` currently fails at the current runtime's `Missing plain-rule attempt pair: NRS-484B-227-1@motor_vehicle_driver`, because both U-turn-through-opening cases are only planned exception attempts. Next, construct a separately sourced prohibited-condition attempt without asserting a legal verdict, extend the fixed-cell comparison and semantic cases, then rerun the stage validator. Continue exact compatibility and saved-processing proofs after that construction. This is unfinished CPU work, not an external dependency.

## 2026-11-25 exact U-turn construction checkpoint

Two exact constructions are selected in `review-draft-manifest.json`; both pass `runtime.py offline` with source-bound logs under `cases/<suffix>/primary-offline.log`. `runner.py --check` passes each case and requires reviewed original Native map, cameras and public-authority document before physical capture. The runner uses `uturn_route.py` for single forward or forward–reverse–forward segments, two realized barrier sections, synchronized four-camera FFV1 capture and original Native body/gear/frame history. `saved_finalizer.py` and both measurement contracts are authored and pass the current runtime's measurement-contract validator; compatibility and saved processing are not yet proven. Focused tests pass geometry, phase control, original gear capture and negatives. C126120 remains **partial**. The next CPU actions are case-specific source-shaped fixture recipes, positive/negative compatibility, recorded-only saved processing, physical outcome fixtures, assessed fallbacks, semantic proposals and independent delivery/comparison audits. Original map, motion, camera pixels and authority status remain for local review.

## 2026-11-25 U-turn route construction checkpoint

Both exact selected U-turn cases now have `cases/<suffix>/route-plan.json` with explicit single forward or forward–reverse–forward segments and a `uturn_route.py` Native segmented controller. The route validator checks complete-body clearance through the authored opening, two barrier footprints, joined movement phases and approximately 180-degree final heading. Its tests reject blocked-divider crossing and disconnected reverse motion, and exercise Native reverse control. The focused CPU suite passes. These plans are marked authored CPU diagnostics: no actual map, public-authority document or Native completion is claimed. Next worker CPU work is the exact runner and four original cameras, then saved finalizer, semantic proposals, source-bound offline/compatibility/saved proofs, physical preparation, fallback and independent audits. C126120 remains partial.

# C126120 CPU handoff — NRS 484B.227(1) U-turn

Status: **partial**. Fixed cell: median opening, U-turn and median barrier. The law permits crossing or turning through an opening, crossover or intersection established by public authority. The selected branch includes a multiple-movement U-turn.

`case-plan.json.evidence_review` reads both accepted metadata inventories. They identify opposite-roadway/right-roadway cases, 556 frames and a passing decoder, but no exported raw trace, video or audit proves a U-turn or authority-established opening. No original is replayed or claimed sufficient. Conditional new U-turn cases retain that gap.

`barrier_construction.py` calls Native `world.try_spawn_actor` for two barrier sections, checks realized footprints straddle and do not close the opening, then cleans up. `uturn_measurements.py` joins original frame/body/gear records, detects opening and blocked-divider overlap, start/end roadways, heading change and forward-reverse-forward movements. Three CPU tests pass, including a negative divider crossing, stale frame, missing gear and Native cleanup. Turn angle and gear changes are descriptive; authority status and legal result remain unresolved.

Next CPU work: source-review accepted originals for equivalence and public-authority establishment. Construct exact Native U-turn path and controlled multiple-movement sequence; implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions. Actual motion and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C126120__NRS-484B-227-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C126120__NRS-484B-227-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C147311__NRS-484B-220-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

Correction: the multiple-movement observation now requires measured reverse body displacement against the vehicle heading as well as a forward-reverse-forward gear sequence. The revised three-test suite passes; the result log hash was refreshed. This remains a CPU fixture, not physical U-turn evidence.
