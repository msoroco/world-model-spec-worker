# training__C230259__LVMC-11-30-060-A__pedestrian

Status: **partial**. Probe_02 is a selected CPU draft and probe_01 its controlled comparison draft. Neither is delivery-ready; no Native CARLA execution or accepted recording is claimed.

The frozen cell is `road` / `travel` / `other_vehicle`, pedestrian subject. Exact LVMC 11.30.060(A) requires yielding to all roadway vehicles when crossing outside a marked or unmarked intersection crosswalk, except when Section 11.30.070 designated-place prohibition applies. No accepted recording ID is supplied. No legal yield or applicability conclusion is inferred from requested timing.

## Native construction and CPU proof

- `native/draft_road.xodr` authors a straight two-direction road without a marked crosswalk or junction. `native/draft_runner.py` surveys the actual CARLA map for road/lane identity and absence of crossing/junction objects before capture. It spawns one pedestrian and one roadway vehicle. The vehicle retains the same request in both cases; pedestrian departure frame 320 versus 140 is the deliberate difference. The Native path records 600 original post-tick rows, `FrameMap` identities, four frame-joined FFV1 camera streams, source context and measured crossing result. It destroys owned actors and restores the original world. A fake-map CPU test rejects the wrong lane. Physical behavior has not been observed.
- `native/crossing_meter.py` validates complete 600-frame original 20 Hz rows, hash-bound context, the vehicle inventory, pedestrian body occupancy, crossing-category survey and conflict precedence. Existing `native/source-meter-proof.json` documents three synthetic positives and four negatives; those fixtures are not Native motion.
- `draft-manifest.json` SHA-256 `f491c437df5662fc021654925309d83522b86bfede0a6387bd59f7e91f6e853c`; `draft-offline-receipt.json` SHA-256 `76b61300adf30e5a95a8f70a2d80d54545c886bf0d51ad7cd80e4e8a48574107`. Probe_01 construction SHA `d1b3f9b557e5d0e24fcf8413b8659ae2a9348fcd9a6da15e85c642be6d17ec46`; probe_02 construction SHA `5ba99d56c3528a1b6f9539928991731694291150e29bbab00f489c88789ee6a7`.
- Pinned `runtime.py offline` commands in the receipt passed for both cases using `.runtime-work/c230259-offline-03` and `-04`, each running three Native CPU tests. Logs: probe_01 SHA `f68f051f53439e171c500abc451e4d98ccc4557b367188571b4b19c335e3d2ff`; probe_02 SHA `565597c3d5b73f682c70987df3fdda1f243c99ad5d3a4296c949dececc10baba`. No simulation started.

## Open work

Run original Native capture and inspect geometry, all vehicle/pedestrian motion and four-camera pixels. Determine whether Section 11.30.070 excludes the crossing using source evidence. Complete current-runtime positive/negative compatibility and saved processing, Core mapping, semantic proposals, independent delivery/comparison audits and selected fallback constructions. Keep partial until all CPU proofs and strict scoped ready gate pass.
