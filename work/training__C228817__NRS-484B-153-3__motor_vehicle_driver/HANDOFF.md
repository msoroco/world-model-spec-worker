# NRS-484B-153-3 at C228817

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `load_unload` / `other_vehicle`.

Exact statutory source: NRS 484B.153(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Traffic-side door left open during loading or unloading.

Controlled planning variable: `traffic_side_door_open_duration`. Proposed requests: traffic-side door closes when immediate loading ends; same door remains open after immediate loading ends. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: passenger or cargo loading; traffic-side orientation; necessity duration unresolved.

Accepted membership: 4 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current gap: Draft Native constructions and saved-source measurement now exist for two passenger-transfer schedules. Cargo construction, public compatibility, recorded-only proof, semantic stages, physical/lifecycle and independent delivery audits are incomplete. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; finish cargo construction and mandatory measurement mapping, then execute pinned-runtime compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `native/controller.py` requests 600 frames at 20 Hz for the two planned probes, holding ego, passenger transfer, and passing path fixed while changing only the traffic-side door close frame (212 vs 400). This is a CPU policy request; Native actuator wiring and original observations are still required.

`native/measure_door.py` joins contiguous Native frame/time, four source-camera identities, door side and state, selected driver responsibility, passing-vehicle trajectory, stationary ego, and sourced passenger occupancy/pedestrian or cargo transfer. It reports elapsed and post-transfer open time while keeping necessity and immediacy unresolved. Synthetic proof: 3 positive diagnostic variants and 11 negative source/geometry rejections. No synthetic sample establishes legal or physical acceptance.

SHA-256 bindings:

- `native/controller.py`: `cee33d963d4683e1974534c618852cd7b0b87f3ef6406b0e058c0642306bd79a`
- `native/measure_door.py`: `0898bb6f11d658262faac3ac3e6c77166e0647fb9e31fa5fd4b7219ab1eac86e`
- `native/prove_door.py`: `7cbd62f088715883f67b2fdf5807c8fa9ab8ad6ee147541e47a8a7f28f66898d`
- `native/door-proof.json`: `7ba6c21cfa29a2653261c74d0c8bd7907af079515451f1e54e6772201de23138`
- `native/measurement-contract.json`: `d2e6b2ddd5a59ed5ad78986742f372f8b4753b46b6683cf5f76f6b6ab0eeba6f`

Remaining CPU work: exact Native construction and door actuation/capture wiring, four distinct source-preserving candidates where required, offline/compatibility and saved-only proofs, semantic proposal and independent audits, branch/evidence review and comparison. Accepted membership remains metadata only without original source-hashed equivalence. Keep partial until scoped strict delivery gate passes.

## 2026-11-23 independent comparison checkpoint

`native/audit_comparison.py` independently measures both 600-frame trace envelopes and rejects changes to road, actor, passing-vehicle start, transfer event, camera policy, door side, and source identity. It reports the measured door-close difference while leaving necessity and immediacy unresolved. The diagnostic pair measured a 9.4 s difference and rejected eight altered-source or altered-control comparisons. The CLI requires external SHA-256 bindings for both packet files. This is source-shaped CPU proof only; original Native packets and source-camera video have not been captured.

The `case-plan.json` now maps all six source observation terms to explicit Native trace fields and records the independent comparison command and proof hashes. The mapping still needs original Native capture and pixel review.

Command: `.venv-cpu/bin/python work/training__C228817__NRS-484B-153-3__motor_vehicle_driver/native/prove_comparison.py` (exit 0). Scoped checkpoint: `.venv-cpu/bin/python worker_check.py --assignment training__C228817__NRS-484B-153-3__motor_vehicle_driver --complete` (exit 0, static checks passed).

Hashes: `native/audit_comparison.py` 4493ca4a7e514217c3a1ac8e5ab6b7ac1e5c796fea7076d973f60be61efeb0e8; `native/comparison-proof.json` bc3010782f9fedb1aea2e62c45c393710e19ac5bfbe00d4a7754766359c65913; `native/comparison-proof.log` 6180978d15d828c153b23bfff5e32749d7da9de79d0e3e11d3d50fe27647ad45.

Next CPU work: wire an exact CARLA/OpenDRIVE scene and door actuator with source-camera capture into the frozen runtime, then test one primary through offline, compatibility and process-saved before expanding to distinct fallbacks and independent delivery audits. Preserve the four historical accepted recording IDs as membership context until source-hashed equivalence is available. Status remains partial.

## 2026-11-26 exact door actuation checkpoint

`native/door_actuation.py` now applies exact CARLA door transitions at frames 100 and 212/400, while retaining `observed_door_open=None` until independent original source review. It validates SHA-bound Native map, road and transfer records, the frozen cell, selected driver operator, complete passing-vehicle side trajectory, and passenger or identified cargo transfer at frame 200. `native/prove_actuation.py` passed both exact schedules, the cargo source form, and seven negative source/geometry guards. `runtime.py preflight` passed on the pinned CPU environment.

Proof command: `TMPDIR=$PWD/.runtime-work SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c228817 PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -B work/training__C228817__NRS-484B-153-3__motor_vehicle_driver/native/prove_actuation.py`. Hashes: `native/door_actuation.py` 3a0e05adcb06ffc0fde8fb86e687c90f407051d0956196e920cf7f99ee53cc30, `native/prove_actuation.py` 1969530e22a781841e59612e0b7d76b0e088e7d914b01edbffdce9d86a1cb92a, `native/actuation-proof.log` 2295909d941099179133e7b75129b4b01649e4e0b1d686e0677d060150003d29.

Status remains partial. Next CPU work: bundle this actuator in a four-camera Native runner with source-bound actor and transfer capture, then run exact offline/public positive and missing-source negative, recorded-only, semantic, physical/lifecycle and independent delivery/comparison proofs. Accepted membership is not source-hashed equivalence. No legal necessity threshold or physical completion is inferred.

## 2026-11-26 saved-source finalization checkpoint

Both exact door schedules now bundle `native/finalize.py` and `native/measure_door.py` with the Native runner. Their selected case IDs, 600-frame duration, 20 Hz rate, four camera plans, source channels and case identity are frozen in the draft constructions. The current-runtime `runtime.py offline` check passed for `probe_1` and `probe_2`; their logs are `native/probe-1-offline.log` and `native/probe-2-offline.log`. The draft manifest hash is `215cab5248893177828fd2f10bb6472fa11840e822b0536b86d0b77210183b36`.

The saved finalizer requires a separately authored `door-pixel-review.json` for every one of 600 door states, four hash-bound source videos with in-bounds pixel boxes, reviewed traffic-side orientation and passenger/cargo transfer, the original setup source hashes, and contiguous Native actor/frame/time joins. Actuator requests and the planned transfer source do not count as observations. It writes six derived channels, a Native result, and an analysis report with measured open and post-transfer durations and no legal verdict or physical acceptance. The synthetic `native/prove_finalize.py` test passed both close-frame targets (212 and 400), the real runtime's `validate_attempt` on each synthetic Native-shaped result, and twelve missing-source, stale-video, missing-review, wrong-case and pixel/occupancy rejection branches. The synthetic blue frames establish software joins only; original door motion, passenger movement and necessity remain unverified. Proof command: `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c228817-resume PYTHONPATH=$PWD/runtime/scenario_pipeline:$PWD/runtime/python .venv-cpu/bin/python -B work/training__C228817__NRS-484B-153-3__motor_vehicle_driver/native/prove_finalize.py`.

Current hashes: `native/finalize.py` `f262a1359777eac854681625e13eec3f39dd687d266e93efdeab25894769b2fe`, `native/prove_finalize.py` `6c8f57fcb15b61f545286dafe5ed7f261cafc3c52ecac01c5423805530878c9a`, `native/saved-proof.log` `16f0296f117288461c416c4d541fa06076ecfa9cbe3e0d4e8bb11b9e17cf8ff1`, `native/probe-1-construction.json` `4679c6b6ceb8df99537d2707ee0a6850550a58cd97efc9957c8f3ad905db3da5`, `native/probe-2-construction.json` `9c7a1df4437ebb83affc4d81b8c6c5bcc5ca2269ba00d65719edb5564529630b`.

Still required CPU work: implement the cargo alternative as a distinct controlled construction or obtain a source-hashed existing-evidence disposition; build exact generated fixtures and run current-runtime public positive and missing-source negative compatibility and recorded-only processing; author canonical semantic stages, independent physical/lifecycle and delivery audits; then bind a selected execution manifest and run the exact strict assignment gate. Keep result partial until that gate passes.

## 2026-11-26 cargo alternative and four-case checkpoint

`probe_3` and `probe_4` now request the same 212/400 close-frame contrast for an identified cargo prop carried by the walker. The Native runner separately records the cargo actor identity and position; the saved finalizer rejects a cargo annotation that does not identify that original Native actor. These are prospective constructions, not proof that the prop attaches, moves or is visibly loaded in CARLA. The exact selected alternatives now comprise passenger `probe_1`/`probe_2` and cargo `probe_3`/`probe_4`; each pair holds transfer kind fixed and changes only requested door close frame. `case-plan.json` maps the statutory passenger/cargo alternative and both controlled comparisons to these four cases.

Current-runtime `runtime.py offline` passed all four draft constructions. `native/prove_finalize.py` passed all four synthetic saved analyses through the runtime Native `validate_attempt` plus 24 negative guards; `native/prove_comparison.py` passed both passenger and cargo interval comparisons plus 16 negative fixed-condition/source checks. No synthetic measurement is a legal necessity threshold. Draft manifest SHA-256: `3000ceda6b04044298f83f888d6dbff79ce1ea5b7fbb10636186d42f15cfca13`. Comparison audit SHA-256: `1d1f3552c8e89758944a02c7e6296738d767b84d3d1ab10ce25b3ef83176aef6`; proof SHA-256: `22093f00a363b183dda1379c0e60e6701c2991bd40120dcc148bad82a5e7db32`; log SHA-256: `6774018dc8621e20184532dac824aa26c3311e30db658ab3f6aa56311f472fff`. Saved proof log SHA-256: `2a9a75186258ccd56e0983a3e7786a5ce1754f1f2a2b12a3448c80a98b2a4a07`.

Next CPU steps remain: exact generated fixtures and current-runtime public compatibility positive/negative, recorded-only tests, canonical semantic proposals, physical/lifecycle and independent delivery audits, selected execution manifest and strict assignment gate. Reassess the cargo prop availability and visibility with original Native readback and pixel review at local execution; this is a physical check and does not substitute for remaining CPU code.

## 2026-11-26 current-runtime selected preparation

This section supersedes earlier task lists and hashes. All four selected 600-frame, four-camera diagnostic recipes passed public `runtime.py compatibility` positive and missing-source negative checks with the current sealed-runner construction hashes. Their exact offline checks passed. The selected eight-stage semantic chain passed `semantic_delivery.validate`, covering traffic-side geometry, independently reviewed passenger/cargo transfer, and contextual necessity with two controlled 212/400-frame judgment sweeps. Those frames are engineering requests, not legal thresholds. `worker_check.py --assignment ... --complete --require-delivery-ready` currently reaches the final partial-status gate.

The prospective Native runner now writes original provenance and seals 600 frames only after all four encoder exits and world-restoration readback succeed. Four synthetic physical fixture triples and ownership-order checks pass the runtime physical-preparation validator; they establish CPU decision behavior, never actual Native movement. Each case has a same-case fallback with slower commanded walker speed, triggered only when original reviewed transfer pixels fail to resolve actor and event. All four fallback offline and public compatibility proofs passed; receipt binding is being finalized.

Current remaining work: finish saved-only checks against the stable final manifest; bind independent delivery audit proofs; materialize canonical root runner/config/construction/tests and exact camera plan; align case-plan and comparison IDs; rerun exact scoped strict check. Keep partial until it passes. Original physical door pose, actual transfer, and legal necessity remain pending local source review.
## Final CPU delivery-preparation verdict (2026-11-26)

The four selected primary cases and four same-case physical fallback constructions have source-hashed current-runtime offline and public compatibility receipts. Each selected case has a passing recorded-only positive and missing-source negative proof, exact-law semantic evidence, synthetic physical/lifecycle receipts, and independent delivery acceptance positive/negative selftests. Canonical 30-second synchronized four-camera root artifacts and four root CPU tests pass. The exact scoped command `.venv-cpu/bin/python -B worker_check.py --assignment training__C228817__NRS-484B-153-3__motor_vehicle_driver --complete --require-delivery-ready` passed with `TMPDIR` and `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/`; its output reported `static_checks_passed: true`.

The 212/400 close frames are controlled engineering contrasts, not statutory time thresholds. Their command schedules do not prove actual Native door state. Later original-source review must bind the door closest to passing traffic, observed open interval, contemporaneous passenger/cargo transfer, and whether the interval was longer than necessary for immediate loading or unloading. Four accepted recording IDs remain metadata-only and are not reused as source evidence.
