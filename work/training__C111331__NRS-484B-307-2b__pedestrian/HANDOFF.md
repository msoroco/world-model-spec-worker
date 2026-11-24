# NRS-484B-307-2b at C111331

Actor: `pedestrian`. Frozen cell: `intersection` / `travel` / `traffic_light`.

Exact statutory source: NRS 484B.307(2)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Pedestrian travel across a highway. Planned comparison variable: `contrary_pedestrian_signal`. Requests: pedestrian enters marked crosswalk on circular green with no contrary pedestrian device; pedestrian enters on circular green while governing pedestrian signal directs otherwise. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the signal facing the pedestrian shows circular green alone; the pedestrian crosses within a marked or unmarked crosswalk.

Timing to retain: the permission is read from the indication at entry; a change of indication during the crossing hands the case to the pedestrian-signal rules.

Exceptions and numeric alternatives planned: where a pedestrian signal directs otherwise, the pedestrian-signal rules govern.

Unresolved judgment or rule composition: this line is a permission, so a violation can only be of the rules it defers to. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU saved-entry measurement checkpoint

Implemented `saved_entry_measurement.py` over 600 joined raw signal and pedestrian-pose packets at 20 Hz. It measures the crosswalk entry frame, circular-green state at entry, governing pedestrian-signal state, and the crossing interval; it emits no legal verdict. `prove_saved_entry_measurement.py` passes four synthetic scenarios (walk, contrary device, signal change after entry, red at entry) and rejects seven missing or mismatched source conditions. This is a CPU diagnostic with synthetic packets and camera IDs only; it contains no source-camera video, Native provenance or physical observation.

Command: `.venv-cpu/bin/python work/training__C111331__NRS-484B-307-2b__pedestrian/prove_saved_entry_measurement.py > work/training__C111331__NRS-484B-307-2b__pedestrian/saved-entry-diagnostic.log` (exit 0). Receipt `saved-entry-diagnostic.json` SHA-256 `77f1b57ea1f70cd52d41d109716e8c887752151d15c9ec393a3956b42dc640af`; log SHA-256 `7c67f29351e081ab13635f65fd81b307fa15d7766a868308dc57f60558330fd9`; script SHA-256 `3ebd818cf3dd040f63fc74c34a1536ccce8e963ff69383ec3723abb3597a6892`. Pinned `runtime.py preflight` and assignment `worker_check.py --complete` exited 0 this turn.

Next CPU work: build the exact Native construction and all four named video captures for the primary selected case; bind this raw-source measurement to the actual saved-processing adapter; run exact offline/compatibility positive and negative proofs; add selected fallback constructions, semantic proposals, and independent delivery/comparison audits. Keep `partial` until the scoped strict delivery gate passes.

## 2026-11-23 Native crossing construction checkpoint

Added four exact unselected construction bundles in `draft-native-bundles/`, one for each planned witness and exception case. `native/construction.py` binds the pedestrian, four current-profile cameras (1920×1080 overview; three 1280×720 views), 600 frames at 20 Hz, a marked crosswalk and named traffic/pedestrian heads. It holds those conditions fixed across both comparisons and changes only the requested pedestrian indication. `native/road.xodr` authors two crossing roads and signal/crosswalk objects; the intersection junction connectivity and physical signal support are not verified by CPU checks. `native/runner.py` has a guarded Native capture path with an exclusive-world check, four original RGB FFV1 streams, per-frame Native pose/light readback, camera hashes, cleanup and world restoration. It does not claim that the authored indication is visible or governs the walker. The physical display and pixel interpretation must be independently reviewed after a Native attempt.

`prove_native_construction.py` passed an authored map/comparison check and a 600-frame structural Native/camera hash join, then rejected five missing or mismatched source conditions. The source join checks declared hashes; it does not decode the full videos or verify that pixels depict a qualifying signal. Proof receipt: `native-construction-cpu-proof.json` SHA-256 `553a8820de7202452435f86cdb5b927b77ddc99d4c463f344760fb131088e820`. Four pinned `runtime.py offline` primary bundles passed without simulation; exact construction and log hashes are recorded in `native-cpu-checkpoint.json` SHA-256 `68e3844469b9dff48dc8e4e263c7a850da8cb6f2920a1c7da88ca5f9a7534194`. Draft manifest SHA-256 `d871dcb0fc0249f8756cfa4dad9c4addb1980193f182a207a5cc3717e53b32ca`. Pinned preflight and assignment `worker_check.py --complete` exited 0.

This is still `partial`: the Native intersection geometry and signal heads need run-time readback, governing direction and original pixel proof. The original saved-entry diagnostic uses old camera names and synthetic packets; it still needs current-profile Native packet integration. No selected measurement contract, exact positive/negative compatibility, saved processing, fallback, semantic proposals or independent delivery/comparison audit exists. The permission cannot itself be treated as a violation, and the cited NRS 484B.283 rules require separate source review. Keep all physical and legal outcomes unknown.

## 2026-11-24 current v2 primary CPU checkpoint

This section supersedes the older gap statements above. The four current-camera Native drafts still pass pinned offline checks. The runner now resolves two distinct OpenDRIVE signal actors (`201` circular head and `202` pedestrian head), samples their Native state each frame, and fails closed when a head is missing, ambiguous or has an unrecognized state. This is source readback design, not proof that an original camera depicts the intended indication or that either head physically governs the crossing. The revised source bridge requires 600 joined Native samples, four complete decoded source videos, exact frame/timestamp identity and observed signal readback. Its synthetic diagnostic passes two positives and rejects three invalid-source cases; `saved-source-bridge-proof.json` SHA-256 `e2443d3360a0dc4c13e5879300bbd87f56b796ff60fff1b45201cc92b2606e27`.

Built one exact source-hashed current v2 primary witness_1 diagnostic. `v2-primary-manifest.json` SHA-256 `d549069f4dca5f03b7b022ce4531bc3322946a2f380cb4afbcceb40e1b0874b2` binds construction SHA-256 `95edf3314f99d310fdb69f64b31b669aa1cba057fb7d0163ee092d08de504188`, recipe SHA-256 `9b8692c64d6d39b1490fd653533898bbf0c817e2c35536245a4b476f95a9784b`, seven explicit retained source files, 600 generated diagnostic graphs and four 600-frame FFV1 videos. The source packet and videos are synthetic diagnostic evidence; `native_provenance` is false and no physical or legal outcome is asserted. The saved finalizer measures entry at frame 230, exit at 291, circular green and `walk` at entry from joined retained packets. It writes a separately identified derived observable stream and leaves original acquisition unchanged.

The exact current manifest also passed pinned `runtime.py offline` without starting simulation; retained `v2-primary/witness_1/proofs/primary-offline.log` SHA-256 `1fdadefb72f5be6aeaa2ab3275da53f8c9b796613076797ebe6e5f96015969a8`.

Pinned `runtime.py compatibility` passed all 11 public checks, including Native validation, replay adapter, Lean decoder, render, complete final video decode, selected measurement and missing-source negative. Durable receipt: `v2-primary/witness_1/proofs/compatibility.json` SHA-256 `78abf41cf90cc4f073c2fa9af441042d383683eb22b81d8a4b646e238a3ce569`. The negative removes `c111331-native-samples.jsonl` and fails with the required missing-source message. Pinned `runtime.py process-saved` then passed from that exact attempt with recorded-only=true, missing_evidence=false, originals_verified and no physical or legal acceptance claim. Durable receipt: `v2-primary/witness_1/proofs/processing.json` SHA-256 `e9f7a3ec5cc6c500816348ed72adf84e5a58351f9879d0f049b3cebdb3d163b3`. `audit-v2-primary.py` independently binds these durable receipts to the current manifest, construction, recipe, analysis report and retained source hashes, using only work/ files.

The saved-entry diagnostic was also rerun using current camera IDs: four positive scenarios and seven negative rejections; receipt SHA-256 `c47ca548b20557419085bc98cb9804a46f3027e0dd8693f7a29abde09905dd30`. Older hashes in the sections above are historical. The primary remains unselected and `partial`: no actual Native attempt or verified original signal pixels/governing direction, no source-law review of the NRS 484B.283 deferral, no current v2 proofs for the other three cases or fallbacks, and no semantic/comparison/delivery audits. Do not infer a violation from this permission branch. The next worker should extend the exact construction to witness_2 and both exceptions, run their public compatibility and process-saved checks, then add comparison/semantic audits and independent original-pixel review.
