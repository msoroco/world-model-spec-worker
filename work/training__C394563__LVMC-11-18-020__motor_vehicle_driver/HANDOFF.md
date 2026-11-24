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
