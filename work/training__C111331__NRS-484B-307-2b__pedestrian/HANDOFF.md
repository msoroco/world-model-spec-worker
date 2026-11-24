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
