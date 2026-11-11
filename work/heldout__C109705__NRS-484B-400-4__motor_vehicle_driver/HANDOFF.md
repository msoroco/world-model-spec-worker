# Handoff: heldout__C109705__NRS-484B-400-4__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a one-way highway onto a two-directional highway, the left turn must be made by passing to the right of the centerline of the highway being entered upon leaving the intersection, and the approach for the left turn must be made as close as practicable to the left-hand curb of the one-way highway.

Cell C109705: intersection / left_turn / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- One-way source highway to two-directional destination, left turn at intersection: compare measured approach body position relative to left curb with held departure.
- Compare destination body position right of entered centerline on leaving intersection with held approach.
- “As close as practicable” has no numeric legal cutoff; retain geometry, body footprints, feasible obstructions and alternative position measurements.

## Current checkpoint

Three cases compare measured approach body distance from the one-way road left curb with departure held fixed, and measured departure body side of the two-way road centerline with approach held fixed. Original four-corner footprints and map lines are required; no practicability cutoff is invented. Tests reject wrong road geometry, absent phases and changed held positions.

Implemented and CPU-tested: turn_geometry.py, turn_comparison_audit.py. The `cpu-tests.log` SHA256 is `3afb3f68b624e9e2d90264cb0c3b196d0a2e3a5c18ae947e08b9bd7a151409df`. These measurements are descriptive engineering observations and do not establish physical visibility or legal compliance. Status remains partial.

## Exact next CPU work

1. Review the new case plan against exact law and source topics; complete any missing alternatives or exceptions while preserving fixed cell/actor scope.
2. Exact Native constructions, four-camera capture, finalizer integration, three fallback constructions per case, offline/compatibility and saved-processing receipts, semantic proposals and delivery audit remain CPU work.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, then `runtime.py process-saved` on retained synthetic sources. Integrate the CPU-tested measurement and comparison audit with exact source bindings, and test independent delivery rejection paths.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C109705__NRS-484B-400-4__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete`. The strict readiness gate still fails because this package is partial; do not mark ready until every exact case and fallback passes its source-bound proofs.

## 2026-11-11 construction and first exact delivery checkpoint

The selected branch is a **one-way approach to a two-directional entered highway**. Corrected stale branch-analysis text that had reversed those directions. `turn_native_runner.py` now chooses a connected left turn through a Native junction with original OpenDRIVE lane directions, commands approach/departure lateral offsets, and retains four synchronized camera streams, map curb/centerline lines and every subject ground-body corner. `turn_finalizer.py` measures the original corner distances from the curb and signed positions relative to the entered centerline. It verifies JSON/JSONL footprint identity and trace/frame-map/time joins before writing two timestamped channels. It asserts neither actual physical completion nor legal practicability.

The first exact case, `approach_near_depart_right`, passes all ten CPU unit tests, fresh offline construction, positive and missing-`road_geometry.json` negative compatibility, and saved-only processing on a marked synthetic diagnostic. Original acquired files were unchanged after saved processing. Proof logs and SHA256 values are recorded in `result.json`; the saved receipt is `saved-first.json`. The diagnostic transfers Core graph and source video material from a prior synthetic fixture and adds C109705-specific map/footprint records; it is **not** an actual Native turn capture.

Status remains **partial**. Next worker CPU steps: construct and prove the `approach_far_depart_right` and `approach_near_depart_left` contrasts; add a finite original-position sweep for “as close as practicable” without a legal cutoff; bind three distinct physical-risk fallback constructions per exact case; run offline, positive/negative compatibility and saved processing; then run independent source comparisons, physical fixture outcomes, delivery audit and scoped strict readiness gate. Actual Native motion, camera visibility and legal practicability remain later checks after CPU preparation.

## 2026-11-11 three-primary contrast checkpoint

`expand_contrasts.py` binds current construction source for all three exact cases. Each primary has a distinct selected config, marked synthetic geometry/footprint diagnostic, measurement contract and source recipe. All three pass fresh offline and positive/negative compatibility proofs, then saved-only processing; saved receipts attest original acquisition bytes unchanged and make no physical or legal acceptance claim. `prove_contrast_comparisons.py` independently checks the near/far approach contrast with destination side held, and the right/left departure contrast with approach held. Its negative mutation changes the held departure and is rejected. The corresponding hashed proof logs are listed in `result.json`.

The assignment remains **partial** because a finite practicability sweep, three physical-risk fallbacks per exact case, source-shaped physical outcome fixtures and independent delivery audits have not yet passed. The diagnostic body footprints are authored CPU inputs, not evidence that CARLA drove the selected turn.

## 2026-11-11 six-case candidate and saved proof continuation

All six exact primary constructions and 18 distinct physical-risk fallback constructions now pass the pinned `runtime.py offline` and positive/missing-source `runtime.py compatibility` paths. The 24 proof records and exact current construction hashes are in `candidate-proofs.json` (SHA256 `c8cc49a5010321943524b02819ff33532ce5a1c11aea7e877c97aae5b8ce6786`); run `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C109705__NRS-484B-400-4__motor_vehicle_driver/prove_candidates.py` to reproduce in fresh ignored attempt directories. The script preserves earlier attempts.

All 24 constructions also pass synthetic `runtime.py process-saved`, with original acquisition files unchanged; `saved-candidate-proofs.json` SHA256 is `aed1a6afcb55f20c60864e06b220df1bf99fb7927f68151dc6960921d5e80b85`. Run `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python work/heldout__C109705__NRS-484B-400-4__motor_vehicle_driver/prove_contrasts_saved.py`. These marked diagnostic videos and footprints are software fixtures, not actual Native turn or pixel evidence.

The independent comparison audit now rejects a changed held departure position even if both samples remain on the same centerline side, and checks both approach curb-distance bounds when approach position is held. `prove_contrast_comparisons.py` and the assignment unit suite pass. `case-plan.json` now includes the finite three-case approach practicability comparison; `prove_practicability_grid.py` compares all three pairs and rejects a same-side held-position mutation. Its source-bound proof is `practicability-grid-proof.json` (SHA256 `223e57dd4d381d9a1d2dad936186b3a66a01fe830310c268dfd82f213bd261ef`). No numeric legal practicability cutoff is asserted.

Scoped `worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete` exits 0 (`worker-check.log`, SHA256 `783b13007318ea86d41503dc1edfa322ddd924f101df6f9e49876e0886a81d97`). Scoped strict readiness exits 1 because `result.json` remains truthfully partial (`strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). Next CPU work: source-shaped physical/lifecycle complete and incomplete fixtures; canonical semantic stage proposals; independent delivery audit with positive and stale/missing-source rejection; finalized execution manifest and queue binding. Reprove any construction or finalizer affected by those changes, then run the scoped strict gate before setting ready. Actual CARLA motion, camera visibility and legal practicability remain later unverified observations.

## 2026-11-11 independent delivery and physical protocol continuation

Status remains **partial**. `turn_delivery_audit.py` independently recomputes the exact one-way-to-two-directional left-turn geometry from retained `road_geometry.json` and `body_footprints.json`, joins original JSON/JSONL body rows to the 20 Hz trace and frame map, checks analysis source hashes, and fully decodes all four named source cameras. `prove_turn_delivery.py` passes positive audits for all six selected primary cases and rejects a changed original road geometry file in each case (`turn-delivery-proofs.json`, SHA256 `87c7ded3e357f2e7399611d70f9211f314172365be781bb1f5d9cdd86663ef93`; aggregate log SHA256 `1030298e68de09dca4e130bf605c36dbb2bf1e1ee3a26f69361882dbc2919630`). The diagnostic source videos and footprints are synthetic; pixel visibility and physical motion remain unverified.

`turn_physical_fixture.py` now tests three source-shaped outcomes for each selected exact case: complete approach/departure body phases, missing departure phase, and missing body evidence. `turn_lifecycle_fixture.py` exercises sealed camera/encoder closure, restoration, Native exit, owner release and saved-only processing in order. `prove_turn_physical.py` passes all six sets and writes `turn-physical-proofs.json` (SHA256 `96ba4692b977348cd8e60c884fda4840adfca3caf9b0d9c7ae8111ee8f660072`; log SHA256 `a643e7eee539ec82161f20fe5ca8f2a0baa9b93ea34d34888e67296f69d570f9`). The pinned `physical_preparation.validate` accepts all six current receipts when bound to their exact probe-manifest constructions. The fixtures explicitly state `actual_native_capture: false` and make no legal or physical acceptance claim. Ten local CPU tests still pass.

Next CPU steps are to author the canonical source-backed semantic stage chain and final nine-stage execution-manifest bindings for six primaries plus their three fallbacks, attach these physical and delivery receipts to each exact manifest case, and rerun the affected offline, compatibility, saved and independent comparison proofs. Then run the assignment-scoped strict readiness gate. The shared queue and integration proof remain batch-level CPU work. Do not mark ready from these component proofs.

## 2026-11-11 scoped strict delivery-ready result

This section supersedes the earlier C109705 partial checkpoints. The exact frozen NRS-484B-400(4) branch is a left turn at an intersection from a one-way source highway onto a two-directional entered highway. The six selected cases cover source-left-curb approach distance (`__approach_near_depart_right`, `__approach_far_depart_right`), right versus left of the entered centerline on departure (`__approach_near_depart_left` paired with the near/right case), and a predeclared 1.25/1.75/2.25 m engineering approach-position sweep (`__approach_practicability_grid-0000/0001/0002`). These values are physical setpoints, not a legal practicability threshold. `case-plan.json` records three fixed-condition comparisons, source-observation mappings for all seven frozen terms, a four-camera/duration plan, and the empty accepted-evidence inventory.

All 24 current primary/fallback constructions have inline exact configs. A stale root-config source reference was removed from variant bundles and the builder so case-specific config bytes are not falsely attributed to the root. Every affected offline and positive/missing-source compatibility proof was regenerated (`candidate-proofs.json`, SHA256 `e3de0117c73ac0d0a9e9df4c13eb0f3b0f0b8f2b00b69e5c4a9621a25cf56d35`). The canonical six-case execution manifest is SHA256 `266d7f15ca1ed63e0d81e069478043cad5df2b5922b479f4b8bedccf3173fc64`; its three risk-triggered fallbacks per exact case retain the fixed law/cell/actor, recording contract, four cameras, 20 Hz and duration. The canonical semantic stage index is SHA256 `a28215783afce167a230037755aa1bde4bcc9a766b27e1addb6ef95c391f6b47`; it quotes the frozen law, retains the qualitative “as close as practicable” judgment, and binds the finite physical sweep without inventing a legal cutoff.

All 24 canonical-manifest saved-only receipts pass with retained original source bytes unchanged (`delivery-saved-candidate-proofs.json`, SHA256 `10d05f531310fcf28e19b9451c654961dff3868a646ae90213e73dcdcf0c7399`). `turn-delivery-proofs.json` (SHA256 `4f29b571347ad01c967bb68b3688548baf2430de001c698ed996369028a021d3`) binds six independent positive/stale-original source audits that recompute geometry and frame joins and decode four cameras. `turn-physical-proofs.json` (SHA256 `5f560de2dcc62cf046b0bfe0a150cda8dbf2fe6b3f369d32627ea0afd4b4135a`) binds six sets of synthetic complete, incomplete and missing-evidence source outcomes plus ordered Native exit/owner-release/saved-processing lifecycle. The pinned execution, semantic, compatibility, physical and delivery validators pass (`delivery-validation.log`, SHA256 `7a645b3b6bd526de13ed857c2c03befc54cd43c3f182a241d159d29d63ec916e`). The original source comparison and practicability grid audits were rerun after the inline construction repair.

The exact command `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-4__motor_vehicle_driver --complete --require-delivery-ready` exits **0** (`strict-gate-latest.log`, SHA256 `783b13007318ea86d41503dc1edfa322ddd924f101df6f9e49876e0886a81d97`). `result.json` is `ready / delivery_prepared` only on these CPU proofs. Local GPU commands must still select each exact case and physically verify the one-way/two-directional map geometry, actual left-turn path, body-to-curb/centerline relationship, all four source camera pixels, and duration; an independent reviewer must resolve legal practicability. No synthetic fixture or successful process exit establishes physical or legal acceptance.
