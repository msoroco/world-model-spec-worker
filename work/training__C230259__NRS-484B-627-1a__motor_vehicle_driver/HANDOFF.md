# NRS 484B.627(1)(a) at C230259 — CPU checkpoint

The fixed actor and cell are `motor_vehicle_driver`, `road` / `travel` / `other_vehicle`. The exact law and witness are in `case-plan.json` and frozen `inputs/`; no accepted recording is available for reuse. Activation depends on slow operation that impedes traffic immediately behind, one highway travel lane in each direction, and enough paved width. Extreme-right placement and conditional NRS 484B.630 compliance are distinct. Speed, gap, duration and distance from the edge are measurements, never legal cutoffs. Public-highway status, actual causal impediment, sufficient paved width and NRS 484B.630 applicability require independent evidence.

## Constructed CPU work

`build_draft.py` generates paired primary and `fallback1` constructions under `draft-slow-traffic/` for `__controlled_1` and `__controlled_2`. Primary subject speed, follower policy, map, cameras and duration are common; controlled_1 requests rightward movement, controlled_2 holds lane center. The shared fallback changes the initial follower gap from 18 m to 14 m only if original early gap evidence shows the follower remains more than 15 m behind. Both comparison cases have the same fallback. The one-lane-each-way OpenDRIVE has a 3 m right paved shoulder and explicit edge. `native/runner.py` surveys it, runs the shared `PipelineCapture` original Core and graph collector, captures 600 same-frame participant/body/controller samples, writes the four runtime-named lossless cameras, and seals acquisition after restoration. CPU checks establish code paths, not physical realization.

`finalize.py` requires the source trace, Native lane context, map, 600-frame map, Core trace, original evidence and graph joins and fully decodes the four camera streams. It writes source-hashed diagnostic measurements and a non-accepted result. `audit_comparison.py` independently checks fixed map, highway context, policy, time and camera sources while measuring rightward versus lane-center contrast. `measurement-controlled_1.json` and `measurement-controlled_2.json` bind the selected requirement to the saved observation and specify a missing-context negative source. None asserts a legal verdict.

## Checks run on current runtime

- Preflight, recorded-only measurement proof and independent comparison proof passed. Their source hashes are in `result.json`.
- All four current offline constructions passed `runtime.py offline`; current primary construction SHA-256 values are `5cc175ee968573da588bc3d75c34866e989871affb777fd6d16549655a9a3dc3` and `fd7d9595ad9523b0833754274fe206ebe7d471556697d92af6239207057dcfe9`.
- Public compatibility passed for controlled_1 primary, controlled_1 fallback1 and controlled_2 primary. Each retained `compatibility.json` reports `passed: true`; the paired positive and negative analysis logs are in `compatibility/`. These used source-hashed 600-frame diagnostic fixtures and the current decoder adapter. The sources are synthetic and do not establish physical traffic or legal facts.
- `runtime.py process-saved` passed for controlled_1 primary; `saved-controlled_1-primary-processing.json` reports `passed: true`, `recorded_only: true`, original source checks and 600 decoded review frames.
- Assignment-scoped `worker_check.py --complete` passed static checks. The strict `--require-delivery-ready` gate rejected the truthful partial status with `Preparation acceptance failed: partial/missing packages remain`.

## Exact remaining CPU work

Run public compatibility for controlled_2 fallback1; saved-only processing for controlled_1 fallback1 and controlled_2 primary/fallback1. Bind source-bound receipts into the selected execution manifest, run candidate selection and independent delivery audit, author canonical semantic stage proposals and source-backed comparison audit, then rerun the exact scoped strict gate. The current draft manifest and `result.json` remain partial until that gate passes. Actual Native motion, public-highway and paved-width status, actual impediment, camera pixels and legal conclusions remain unverified.
