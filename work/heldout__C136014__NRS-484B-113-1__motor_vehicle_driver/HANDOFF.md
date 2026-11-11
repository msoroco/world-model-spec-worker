# Handoff: heldout__C136014__NRS-484B-113-1__motor_vehicle_driver

## Exact frozen scope

NRS 484B.113(1): a driver shall not back unless the movement can be made with reasonable safety and without interfering with other traffic. C136014 is a narrow road reverse maneuver with another vehicle; actor is `motor_vehicle_driver`. The law supplies no numeric safety or interference cutoff.

## Current CPU construction and proofs

Three exact cases isolate (1) clear traffic with steady speed, (2) close traffic with steady speed, and (3) clear traffic with braking. Every case has a Native CARLA runner, four synchronized cameras, raw backing history, a source-bound finalizer, a measurement contract, a diagnostic recipe, and three distinct risk-triggered fallbacks. All 12 primary/fallback bundles passed `runtime.py offline`, positive and missing-source `runtime.py compatibility`, and positive and missing-source `runtime.py process-saved` with the pinned Lean decoder. The associated logs and SHA-bound compatibility receipts are in `execution-manifest.json`. These are synthetic CPU fixtures, not physical backing acceptance.

`comparison_audit.py` independently joins original history, trace and video-frame map, recomputes reverse motion, minimum center distance and traffic speed change, checks fixed road and ego trajectories, and rejects swapped case sources. `delivery_audit.py` checks exact case identity, both participant sources, full frame joins and four complete video decodes; `prove_delivery_audit.py` confirms removal of `backing_history.jsonl` is rejected for each case. The fixture's `physical_completion_check` is false, so these proofs claim no actual physical or legal acceptance.

Draft `relevance_batch`, `relevance`, `template`, two `judgment_observables`, and `bindings` proposals pass `batch_pipeline.stages.validate`. The existing `proposals/cases.json` is still a noncanonical planning draft (`selected_branch` cases, no baseline/judgment sweep), so no semantic index is asserted.

Eight unit tests pass (`cpu-tests.log`). `.venv-cpu/bin/python worker_check.py --assignment heldout__C136014__NRS-484B-113-1__motor_vehicle_driver --complete` passes. The scoped strict `--require-delivery-ready` check fails because `result.json` truthfully remains `partial`.

## Next CPU work

1. Author and validate a canonical cases proposal: complete variable maps, shared baseline, exact three selected cases and law judgment sweep plan. Keep its recording descriptions identical to the exact constructions; if a required observation is absent, add the source channel and rerun affected exact proofs.
2. Implement three measured physical outcome fixtures (`complete_motion`, `incomplete_motion`, `missing_evidence`) and capture lifecycle proof for each case; bind source/log hashes as `physical_preparation`. The current direct execution-manifest validation stops at the first missing physical preparation receipt.
3. Run execution-manifest, semantic-delivery, package-compatibility, independent delivery and comparison validations; repair concrete failures. Re-run all scoped CPU proofs after any construction/manifest changes. Mark `ready` only after the scoped strict gate passes.

## Current limits

No Native CARLA run or original physical road/camera evidence has been accepted. CPU compatibility and saved processing establish software behavior and rejection paths only. The independent audit still requires visual subject/body review on real four-camera output after execution.
