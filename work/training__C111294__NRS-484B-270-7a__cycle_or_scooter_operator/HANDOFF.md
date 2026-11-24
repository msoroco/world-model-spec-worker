# NRS-484B-270-7a at C111294

## 2026-11-23 current-runtime 30-second checkpoint

The Native proposal, two synthetic interaction sources, saved finalizer and all eight draft constructions now use 600 frames at 20 Hz (30 seconds). The four camera sources use the pinned `overview`, `approach`, `reference_corner`, and `driver_reference` names. The full-resolution diagnostic fixture now writes JSON adapter graphs instead of obsolete pickle graphs. The saved finalizer derives four recording channels from retained `native_samples.jsonl` and `video_frames.jsonl`; it rejects any supplied channel that disagrees with those sources. No original CARLA motion or pixels are claimed.

Current CPU proofs (SHA-256): `synthetic-interaction-proof.log` 1019aaac1953b8244c9332fbd328861b79e3954521f550eb062e2a3d1b05ce9e; `synthetic-interaction-audit.log` 51d513f8a86915a6a7a28ef2e44b593bd70ac7678a0b530779c1138e8b07ae0d; `saved-fixture-proof.log` f8a088bbb9430f0a939442d01afaae0bba90f560b3cd252a41509d8e4389a490; `saved-fixture-audit.log` 0bd592785832010e97a1e321779699c67e0890292b410193cc03fc9a2115998d; `original-shape-proof.log` f73e6c4a4b0a14355cdcd5fdc04fa0872ea1e085a429c68ed2851597a1dff767; `pinned-offline-proof.log` 2d879c8977583a71fe41898931de6daf7b01985e427be57d53083dc45d1ef872 (all eight exact draft constructions exit zero). The current draft manifest SHA-256 is e010283619999f9fe12b3119d149c33817e3edd8cf016729b7167e4dddf9a6c8.

The v1 portable package receipts below are historical after the runtime refresh and these construction changes. A current-runtime portable run reached Core/Lean but failed with `TrafficSpec decoder rejected output: manifest is not complete`; the exact failing log is `draft-package-proof.log` (SHA-256 07df248084c42b276318cea20afa782391fabc6cc4da5330826cc88ee16272f2). Next worker-owned work: inspect the retained converted manifest and JSON graph source requirements, repair the fixture/converter inputs, rerun portable positive and negative saved-processing, author selected v2 recipe and acceptance audits, then scoped strict gate before any ready status.


Actor: `cycle_or_scooter_operator`. Frozen cell: `intersection` / `travel` / `other_vehicle`.

Exact statutory source: NRS 484B.270(7)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Bicycle operator. The controlled CPU comparison varies `bicycle_path_intervention`: a scripted hold before the motorist crosses versus bicycle entry before the motorist crosses. These are synthetic conduct and effect diagnostics, never an inference of intent or a legal interference verdict.

Activation to verify: the subject is riding a bicycle, electric bicycle or electric scooter; a motor vehicle's movement is affected.

Timing to retain: judged whenever the rider and the vehicle share a conflict; the motorist's reaction follows the rider's movement.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: tier S and 'intentionally': intent is interior state; the rule is a surrogate. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

CPU progress: The authored same-cell intersection road passes the pinned map parser. Two 480-frame source-hashed synthetic bicycle/motorist fixtures, five adversarial checks per case, pinned source-bound measurement contracts, an independent controlled comparison and three distinct source-bound fallback trigger tests pass. The pair holds both actor traces fixed before frame 75, then varies bicycle entry and the motorist's measured braking response. Copied crosswalk/white-cane code from a different law was removed after discovery; it never supplied a valid C111294 receipt.

Native proposal: `native/runner.py` and `native/runner_capture.py` preflight both cases and all four distinct knob sets per case without importing or running CARLA. The proposed execution path authors two through connectors, spawns a CARLA bicycle and separate motor vehicle, surveys road/lane readback, retains original body/pose samples, drives 480 synchronized ticks, records four RGB cameras and Core graphs through `PipelineCapture`, writes source-hashed interaction and channel files, and restores the world. Route lookahead and motorist clearance buffer now change measured Native control requests, and the overview FOV changes the camera profile. A CPU emulation of the original-shaped source path and one full portable Native/Core/Lean/video integration pass. No CARLA run or physical outcome has occurred.

Eight exact unselected construction bundles now materialize the proposed runner, capture module, source measurement, saved finalizer, camera policy and three distinct fallbacks for both planned cases. All eight pass pinned `runtime.py offline` with four tests each. Both 480-frame saved synthetic positives, removed-source negatives, four 480-frame camera feeds and source-bound measurement contracts pass. All eight exact synthetic v1 portable package positives and removed-source negatives pass through saved Native validation, Core, Lean, render and final decode. Independent saved-source, offline bundle and portable receipt audits pass. These are unselected synthetic CPU drafts.

Source-bound fallback extraction now joins 480 saved Native-shaped bicycle/motorist body rows, camera calibration, frame identities, capture hashes and a decoded overview video. Controlled synthetic source changes cross all three trigger thresholds, and altered source hashes are rejected. The camera metric is a body-vertex projection, not pixel visibility. Production trigger evaluation rejects synthetic provenance. The exact current bundle receipts should be used after their refreshed audits, since earlier receipt hashes are superseded.

Remaining worker-owned CPU work: strict selected v2 compatibility, independent selected acceptance, statutory branch closure, measurement and queue eligibility review. Actual CARLA behavior, physical bicycle class and propulsion, original pixels, rider intent and accepted recordings are later GPU observations; none is claimed by the CPU diagnostics. No case is selected or queued.

Resume: construct strict selected v2 fixture recipes and acceptance audits, close statutory branches only with exact CPU proofs, then evaluate readiness and queue eligibility. Retain the listed physical limitations for later GPU validation.

## 2026-11-23 refreshed 600-frame portable matrix

The earlier current portable failure used the stale November 5 Lean decoder executable. The retained converted output and decoder message showed a manifest mismatch; the current local decoder (`.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck`, SHA-256 `8171b4a036096de5245af3f7d360c3cc8b5b23d49285c0a7e02a8302911b886a`) accepts the pinned runtime manifest. The probe and matrix now use that executable without editing the frozen runtime.

All eight exact unselected 600-frame candidate bundles pass the refreshed portable path: actual analysis, Native result validation, mandatory Core observations, Lean decoder, render, final decode, unchanged acquisition, reconstructed channels and four camera sources. Every candidate rejects a missing `interaction.json`; `audit-draft-package.py` independently rechecks construction hashes, runtime identity, receipts, logs and negatives. Matrix log SHA-256 `e9f2cdc7303d4656a330ffad6e1d8eb54337dc62333dbf6d43b7b9922601415d`; summary SHA-256 `063a2553fd73b0b23478225fceb5d45616b7116055a6fad701b98dae12b84ce8`; audit log SHA-256 `6a5f852a43b49e9c263e7ba6c6c8ca9416a77401fbe586307d5e78de32a4fca3`. Both primary pinned offline checks pass, log SHA-256 `dbc7159a4be20079a3ad50d63f1a3cbd8cad62b768702c952e975654acb4ea99` and `d220a23ea99fa02f5e7f75a64a47b0fa54bd8e179e2a5af6c8c49126493eedff`. Scoped complete check passes, log SHA-256 `cc0be0717ccf9e4c61100a64008bec7c3c3b537a3a8b3941c064074e8a484afc`.

These are synthetic v1 package diagnostics and do not establish selected v2 delivery, a physical bicyclist or motorist interaction, rider intent, legal interference or an accepted recording. Next CPU work: source-hashed current v2 recipe, selected-case compatibility and process-saved, independent acceptance/comparison audits, statutory branch review and ordered queue. Result stays partial.

## 2026-11-24 current public v2 primary checkpoint

`build-v2-primary.py` authors two exact, unselected 30-second primary manifests. Each has a source-hashed fixture recipe, ten retained source files, 600 generated adapter JSON graphs and four full-resolution lossless diagnostic cameras. The construction changes only its saved finalizer binding: a thin top-level `measure` wrapper calls the existing imported measurement function, satisfying the current static measurement contract without changing its value. Both primaries pass pinned `runtime.py offline`, current public `runtime.py compatibility` with the required missing-`interaction.json` negative, and recorded-only `runtime.py process-saved`. Both saved receipts report 600 timestamp joins, final decode, no missing evidence and original-source preservation.

The returned `v2-primary/<case>/proofs/` directories contain offline, compatibility, positive/negative analysis, candidate-selection and processing receipts. `audit-v2-primary.py` independently checks those durable files, recipe/source hashes, exact construction and manifest binding, 11 compatibility checks, the negative, saved candidate selection, four cameras and 600 frames. Audit SHA-256: `2bcb50f20f82b872133a5f13f9aa330891f4ea2ec5933173aed3ca094a5ec338`. The ignored scratch fixture is not needed to rerun this audit.

Remaining CPU work: run the six fallback constructions through current v2 public compatibility and saved processing, review the exact statute and comparison, then author selected cases and rebind semantic, physical, delivery and comparison audits. Original bicycle/motorist motion, pixels, rider intent, legal interference and accepted membership remain unobserved. Status remains `partial`.

## 2026-11-24 current public v2 fallback checkpoint

`build-v2-fallbacks.py` creates three distinct one-knob fallback constructions per case under unselected manifests separate from the primary proof manifests. All six exact 600-frame fallbacks pass pinned `runtime.py offline`, current public `runtime.py compatibility` positive and missing-`interaction.json` negative, and recorded-only `runtime.py process-saved` with final decode, 600 timestamp joins and original-source preservation. Matrix summary SHA-256: `9e4a818cc5e036197b46ab870ba3f792dc4f47f9270ddc088fb804c669e21cc6`.

Each fallback returns its exact construction and copied offline, compatibility, positive/negative analysis, candidate-selection and saved-processing proofs under `v2-fallbacks/`. `audit-v2-fallbacks.py` independently checks all six using durable files only, including one-knob isolation, source hashes, 11 compatibility checks, missing-source rejection, saved candidate selection and no physical or legal claims. Audit SHA-256: `70705a288b9d5f51b50b63dc680e413a24ca68e6d81fa38d089a021698ad0338`.

The two primaries and six fallbacks are current v2 CPU diagnostics but remain unselected. Exact statutory and comparison review, selected manifest construction, and selected semantic, physical, delivery and comparison audits remain worker-owned CPU work. No original Native or accepted recording is claimed; status remains `partial`.

## Current selected delivery preparation (2026-11-24)

Two selected human-powered bicycle cases, each with three one-knob fallbacks, have 600-frame source-shaped diagnostic chains. All eight pass pinned offline, public positive and missing-interaction negative compatibility, and recorded-only saved processing. The selected execution manifest passes exact execution, canonical semantic, delivery-contract and package-compatibility validators; controlled comparison verifies 75 fixed pre-intervention frames, fixed road/cameras/configuration, and measured diagnostic motorist brake frames 0 versus 175. The altered-participant negative is rejected. Synthetic physical fixtures cover complete, incomplete and missing motion, plus owner-release order. Selected exact-manifest offline checks pass for both cases without simulation. See selected-v2/validate-selected.log, selected-v2/comparison.log, selected-v2/comparison-negative.log and selected-v2/witness_*-selected-offline.log.

Original Native motion, wheel/propulsion exclusion, pixels, motorist response, rider intent, legal applicability, and accepted membership remain unobserved. The first local command is recorded in result.json.
