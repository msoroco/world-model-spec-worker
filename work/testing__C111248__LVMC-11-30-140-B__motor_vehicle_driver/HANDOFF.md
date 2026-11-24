# testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.140(B) — Any pedestrian who is not wholly or partially blind, or any driver of any vehicle who approaches or comes in contact with a person wholly or partially blind, carrying a cane or walking stick white in color, or white tipped in red, or being assisted by a person with wisdom, shall immediately come to a full stop and take such precautions before proceeding as may be necessary to avoid an accident or injury to the person wholly or partially blind.
Assigned branch(es): Driver approaching a blind person carrying a white cane..
Cell: C111248 (intersection, travel, blind_pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

The full statute was reread. The fixed role is motor-vehicle driver; the cases in `case-plan.json` preserve the white-cane assigned branch and add red-tipped cane and assisted-person cue alternatives, approach/contact observations, full-stop/rolling response, and precaution timing. Five controlled comparisons reuse the white-cane full-stop reference. These are planned cases, not physical recordings or legal outcomes. No accepted recordings exist in frozen `evidence.json`; the case-plan review records that exact gap. No exact-law judgment ranges were inventoried.

`blind_encounter.py` now plans source-gated Native map/route/actor identity and separately requires independent blindness attestation plus carried-cue source. `construct_native` calls adapter map lookup and actor/prop construction with readback and reverse-order cleanup; it does not infer blindness from actor appearance. `measure_saved` validates contiguous original 20 Hz rows and measures approach, stop, proceeding, contact, gap and precaution fields. `audit_comparison` rejects missing evidence and changed fixed identities/capture sample counts. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/tests -v` passed 4 tests; log `cpu-tests.log`, SHA256 87f6f5c69c9b38d907ffb2e1e22f0f9258ad3605993952ce72175d70a89efef0.

Exact strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver --complete --require-delivery-ready` exits nonzero with `Preparation acceptance failed: partial/missing packages remain`; see `strict-check.log`. Continue with exact runner/config/construction bundles for all six cases, canonical stage proposals, case-specific diagnostic recipes and offline/positive/negative compatibility receipts, saved-only postcapture path, independent delivery audits, and source-bound comparison proof receipts. The contact case requires risk review before any physical attempt; the code never commands collision. Do not mark ready until the exact strict gate passes.

## 2026-11-24 saved-only source-binding checkpoint

`saved_encounter.py` now processes a closed original-history JSONL together with separately stored blindness-attestation and carried-cue JSON. A small manifest binds each by SHA256, exact assignment and case, and expected frame count. It rejects missing or escaping paths, changed source bytes, incomplete original history, missing independently stated blindness basis/issuer and a cue without an actually-carried observation source. It invokes `blind_encounter.measure_saved`, retains all source hashes in the output, and explicitly leaves physical acceptance false. This is CPU code and fixture proof only; no such real sources have been acquired for this assignment. The test inputs' issuer and observation names are diagnostic fixtures, not verified real-world attestations.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/tests -v` passed 8 tests in `cpu-tests.log` (SHA256 `844e16c04ebcd8727a453d535f70a4d76c3d76c1f494cc077ca2189167d423cf`). The path can be exercised after a real attempt as `.venv-cpu/bin/python work/testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver/saved_encounter.py --manifest ATTEMPT/saved-manifest.json --output ATTEMPT/encounter-measurement.json`; it is not yet integrated with the canonical runtime process-saved finalizer. Next CPU work: Native 20 Hz controller and capture integration, exact case bundles and semantic proposals, positive/negative compatibility receipts per case, independent delivery audit, and stronger comparison checks across distinct Native run actor IDs.
