# C394563 school-crossing CPU construction checkpoint

Status: **partial**. Exact selected-case Native realization, four original camera streams, source-saved processing, compatibility and independent audit have not passed. No delivery-ready claim.

Law branch: LVMC 11.18.020 prohibits vehicle entry into a displayed School-Xing crosswalk while a person attempting to cross is in the crosswalk on the approach side. The City Traffic Engineer marking authority is contextual; the source says person, not only schoolchild. The authored construction places a yellow 3.6576 m crossing at x=0 and a School-Xing sign at x=-35 m, beyond the 100 ft advance threshold. Original source must verify the marking, sign, person intent and entry.

## CPU work completed

- `native/school_xing_request.py` (SHA-256 `02c5a6817c559072fcf9a45b718188d74534c6db080d030fb8e3becf92282cb4`) generated two distinct 600-frame, 20 Hz, 30-second source requests. In condition A the ego front enters at frame 240 during same-side pedestrian occupation; in condition B it enters at frame 320 after that interval. `native/school-xing-diagnostic-proof.json` (SHA-256 `0097fd2562a2f29a19a8d3089cabf9f823953a53e3199492ecc2de8db040a01a`) records request SHA-256 values and four rejected missing/forged-source mutations. These are authored requests and a diagnostic meter, not Native observations.
- `native/build_draft.py` (SHA-256 `b11273cae3aa1f433e677d690a48ab113c3f3ee8ef3f0f537a161e8893e09948`) built exact unselected offline constructions for both planned case IDs. Construction SHA-256: condition A `c3a3b048f52871b9f2883ec722f7f1340eed442e1ed3e2cdb7f86e4f4178c228`; condition B `0a64d39935b73be0a3797590e74ca2941f4be62891e35b5cba060d5d73aff6cd`. Manifest SHA-256 `9e90019b32019fba4ae0a47389e96d09cdf2ef2f92ca8446e79100f24fd5adc0`.
- Exact `runtime.py offline --manifest native/draft-manifest.json --case <case-id> --output .runtime-work/...` passed for both cases. Returned `simulation_started=false`, so this proves inline package structure and checks, not scene execution. Return logs: condition A SHA-256 `48b53988ce5954bd39a474426345ef4b4e1dee4900534099f755f93c65bc3f16`, condition B `415890e93401a61367e37ebebe52fab506b71985e71421d35f61de4b896c0f03`.
- `native/measurement-contract.json` binds the nine observation terms to original scene/actor evidence and the four named camera streams.

## Worker-owned remaining work

Replace authored requests and unselected offline drafts with real Native crossing geometry, sign, ego/pedestrian controllers and original 600-frame four-camera captures for each exact selected case. Measure source-joined predicates, establish pedestrian intent from original evidence, run selected primary and fallbacks through offline and compatibility, process actual saved positives/negatives, and complete source-alternative and independent comparison audits. Keep status partial until the assignment-scoped strict delivery check passes.

## 2026-11-26 source-bound Native construction checkpoint

- Authored a straight two-direction OpenDRIVE road with a 3.6576 m crossing object, yellow marking attribute and a named School-Xing sign object 35 m in advance. `native/geometry.py` checks exact geometry; a fake-map test verifies original-map object readback, approach/opposing directions and rejects missing sign, changed marking and reversed approach. The CARLA import remains lazy.
- `native/runner.py` now proposes ego and walker spawn/control, a 600-tick synchronized Native capture, four original 1920x1080/1280x720 source streams, exact camera-frame joins, original map survey, restoration and capture sealing, plus a source-bound body-history crossing-clearance criterion. This runner is an executable proposal; no CARLA attempt occurred here. The sign object may not render legible School-Xing text; pixel evidence and City Traffic Engineer authority still require independent local review.
- `native/saved_source.py` and `native/finalize.py` source-join original body, person and camera frames; measure first ego front crossing entry and same-side person occupation/motion; reject authored/synthetic source in production; and compare occupied versus cleared entry while checking fixed sign geometry and person identity. No legal intent or verdict is inferred from walker motion. Ten CPU tests cover arithmetic and rejected missing/changed source paths.
- Both exact cases were bundled with the new source files in `native/native-draft-manifest.json` and passed `runtime.py offline` on this runtime. These are unselected draft proofs with `simulation_started=false`. Validated exact-case measurement contracts for all three selected requirement dispositions now exist; positive/negative compatibility, saved-only conversion, physical audit, semantic proposals, selected execution manifest and strict readiness remain outstanding.

### Exact current draft bindings

| Case | Construction SHA-256 | Offline log SHA-256 |
| --- | --- | --- |
| condition_a | cb9e55a22e9f0bd244ea06c1bbe45394c1a832ef060fc20e87d7d5bc55532181 | dd61b58a9470fe8fb56e9d090a31ed83d0bca36a33c903b8d969e78678dc51da |
| condition_b | 0a19b4e5db1d34a42ef7100aaef6a1bfa36de244b1bd0b6c8f7930da25fcbe43 | 52b8493150d42f348dfb634f2e07bbdf78a5b0e18b5456f292a717f3b1a23b08 |

CPU source tests log SHA-256: `f34b3ee005b293e275ed1658e33a7ef27b453b38f2459b4b1e2a4fa6ed085812`.

Next: materialize exact 600-frame diagnostic Native-shaped sources for each condition, exercise `runtime.py compatibility` positive and missing-source negative, bind the finalizer and source-joined physical criteria in selected manifests, complete semantic/independent delivery and comparison audits, then run the assignment-scoped strict gate. Keep `result.json` partial until that gate succeeds.

- `measurement-contract-condition-a.json` and `measurement-contract-condition-b.json` pass the current runtime measurement-contract validator with three exact output methods and a missing road-geometry negative source. They are draft bindings awaiting selected compatibility receipts.

## 2026-11-26 diagnostic saved-source checkpoint

The two exact 600-frame synthetic recipes are `native/recipe-condition-a.json` and `native/recipe-condition-b.json`. The textual specifications are under 0.5 MiB each; generated source videos and temporary attempts stay under `.runtime-work/`. The saved finalizer completed for both diagnostic attempts, decoded all four 600-frame streams, and produced source-hashed measurements at Native frames 10240 (person in approach-side crosswalk) and 10420 (person cleared). `native/diagnostic-comparison.log` records the independent occupied/cleared comparison and a rejected missing `road_geometry.json` negative source. These are synthetic compatibility diagnostics only; they do not establish physical sign display, official marking, person intent, Native motion or canonical acceptance. The full selected `runtime.py compatibility` and recorded-only `process-saved` receipts remain outstanding.

Diagnostic recipe SHA-256: condition_a `4fb086e916b6f77425f98b210ee8d6f6e2afb00fb32a67138460cd1256ef9973`; condition_b `b0051b2f0409a3fd46f0a689a3f7064697546db1844f794747ef62a88e54f572`. Comparison/negative log SHA-256: `cbcf7c18178d6151254234e9eda1aa8c6b6d2d03b75330c95b8127312600cbb5`.
