# testing__C111329__NRS-484B-287-1c__pedestrian

Status: partial case plan, source measurement and four-camera capture checkpoint. No Native or accepted recording is claimed.

Exact source: NRS 484B.287(1)(c) in frozen `inputs/testing__C111329__NRS-484B-287-1c__pedestrian/assignment.json`; witness 390 is conditional and frozen accepted evidence lists zero recordings. The NRS 484B.290 exception remains unresolved.

## Exact cases and comparisons

- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_operating`: crossing outside surveyed marking with both devices operating.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_marked_operating`: same crossing station within surveyed marked crosswalk.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_inactive`: same unmarked crossing, one device inactive.
- `between_intersections_marking` holds site, station and operation fixed; `both_devices_operating` holds site, station and marking fixed. See `case-plan.json` for source gaps, risks and observation mappings. These are planned cases, not recordings.

## Implemented CPU construction and audit

`site_geometry.py` requires SHA-matched map, route, device, marking and highway sources and exact packet-to-source content equality. It checks two distinct junctions, direct source edge, no intervening junction, route crossing both highway banks, strict station between junction envelopes, authority/placement/purpose/governance fields and operation intervals at both devices, and a complete marking survey. It returns legal adjacency, legal official status and the NRS 484B.290 exception as undetermined. Source record IDs are prerequisites for review, not legal conclusions. `native_route.py` lazily spawns a source-selected CARLA walker and applies route controls with readback and cleanup on rejection. `comparison_audit.py` rejects changed fixed sources and conditions. Both crossing directions are CPU-tested.

`native_observation.py` captures original contiguous 20 Hz world frames, walker positions, and two source-identified device actor/state/operation readbacks. Its saved-only analyzer verifies the exact case and site source hashes, complete frame sequence, device identities, and physical bank-crossing segments. It reports device operation over the observed crossing frames separately from all-frame operation; it leaves legal adjacency, official status, and NRS 484B.290 unresolved. The production default is 900 ticks. Caller must bind the device reader to real Native actors and provide a reviewed source packet; fixture readbacks do not establish physical operation.

The capture now takes four named frame-synchronized original PNG readers using the pinned overview1080-capability dimensions (1920x1080 overview, three 1280x720 detail views), stores one lossless archive per camera, and binds each PNG SHA256 to its 20 Hz observation row. `saved_camera_audit.py` independently verifies all archive hashes, frame maps, per-frame PNG hashes, dimensions and full pixel decodes before returning the saved motion analysis. It rejects a missing camera, archive tamper and changed frame binding. A 900-tick CPU fixture decodes all 3,600 images; it uses tiny injected dimensions and does not establish camera visibility or Native capture quality. The caller must supply real per-frame CARLA camera readers and run the saved audit at the pinned dimensions.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1c__pedestrian/tests -v` passes 27 tests; SHA256 of `cpu-tests.log` is 9caf5bd0833aa492be5815849cdd43e89324ce6feee01b6bd8223bacc021900a. `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete` passes; SHA256 of `cpu-static-check.log` is 2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe. These are source-shaped fixtures, not physical evidence.

`.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` failed with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log` (SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a). The result remains partial.

## Next CPU actions

1. Bind a real map and two device actors to the frozen C111329 scene, validate original map topology and connect the real 20 Hz device and four camera readers for each case. Resolve the fixed intersection layout against the required between-intersection segment without inventing a new cell.
2. Add per-case config, construction, manifests, finalizers, diagnostic recipes and source-bound positive/negative compatibility/offline/saved-only proofs. Build semantic stage proposals and an independent delivery audit.
3. Review the NRS 484B.290 exception and legal meaning of adjacent intersections/official devices independently from the geometry packet. Do not infer them from record IDs or visual appearance.
4. Rerun the tests and exact strict gate; mark ready only after it passes. Physical motion, actual map site, camera coverage and recordings remain later Native checks once CPU preparation is complete.

## 2026-11-23 CARLA readback bridge checkpoint

Added `carla_readback.py`, a lazy bridge from four named CARLA BGRA camera callbacks to the exact frame-indexed PNG readers consumed by `native_observation.capture_observation`. It checks dimensions and byte count, bounds pending callback frames, rejects duplicates/missing frames, and consumes each frame exactly once. Its device reader binds each source device ID to a distinct original actor, reads the actor state, and requires a separate boolean operation-health callback; a color state is not treated as operation evidence. The caller remains responsible for selecting real source-grounded actors/sensors, creating them, setting 20 Hz synchronous mode, and cleaning them up.

`tests/test_carla_readback.py` exercises a full five-frame four-camera capture through the bridge, mismatched/duplicate frames, malformed BGRA, duplicate actor IDs, and missing operation evidence. `carla_readback.py` SHA256 `3cfe8c4da879e96da30f91ecf04857384fdde219f54767868f2ec1c3e13e62e0`; test source SHA256 `12a00586faa0cee246ad1e870c233a6cf416fd36357b3805cbc4a6959e2b535e`.

Pinned CPU proofs: `cpu-tests.log` (30 tests, exit 0) SHA256 `e756aef84bf0b8067efa7dbe42558b926ffb00be2af37186986e2631fd48e6bc`; `cpu-preflight.log` (exit 0) SHA256 `71b5e75c8e8b6dfe5d820a79cd7642e5fe17ba3e034cbe8783eb50859177a352`; `cpu-static-check.log` (exit 0) SHA256 `2abf7d9b524b41a18d47ebab23c461e2017332d5c7c46cc8fd1ca5f9c72dfabe`. Exact assignment strict check exits 1, `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`, because the package remains truthful `partial`.

Next CPU work: obtain/review the exact fixed-cell map, device authority/operation and complete marking survey sources; bind three case-specific runners and finalizers to those sources; create canonical stage proposals and saved-only positive/negative compatibility plus independent delivery receipts. Legal adjacency, official-device status and NRS 484B.290 still need independent source-supported review. No live CARLA or legal acceptance is claimed by the CPU fixture.
