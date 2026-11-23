# testing__C111329__NRS-484B-287-1c__pedestrian

Status: partial case plan and source measurement checkpoint. No Native or accepted recording is claimed.

Exact source: NRS 484B.287(1)(c) in frozen `inputs/testing__C111329__NRS-484B-287-1c__pedestrian/assignment.json`; witness 390 is conditional and frozen accepted evidence lists zero recordings. The NRS 484B.290 exception remains unresolved.

## Exact cases and comparisons

- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_operating`: crossing outside surveyed marking with both devices operating.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_marked_operating`: same crossing station within surveyed marked crosswalk.
- `testing__C111329__NRS-484B-287-1c__pedestrian__midblock_unmarked_inactive`: same unmarked crossing, one device inactive.
- `between_intersections_marking` holds site, station and operation fixed; `both_devices_operating` holds site, station and marking fixed. See `case-plan.json` for source gaps, risks and observation mappings. These are planned cases, not recordings.

## Implemented CPU construction and audit

`site_geometry.py` requires SHA-matched map, route, device, marking and highway sources and exact packet-to-source content equality. It checks two distinct junctions, direct source edge, no intervening junction, route crossing both highway banks, strict station between junction envelopes, authority/placement/purpose/governance fields and operation intervals at both devices, and a complete marking survey. It returns legal adjacency, legal official status and the NRS 484B.290 exception as undetermined. Source record IDs are prerequisites for review, not legal conclusions. `native_route.py` lazily spawns a source-selected CARLA walker and applies route controls with readback and cleanup on rejection. `comparison_audit.py` rejects changed fixed sources and conditions. Both crossing directions are CPU-tested.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1c__pedestrian/tests -v` passed 13 tests; SHA256 of `cpu-tests.log`: 6aa3526ad1e509b87e17e827ad8a5f2c84857c61977d6004f4966609707edabb. These are source-shaped fixtures, not physical evidence.

`.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` failed with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log` (SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a). The result remains partial.

## Next CPU actions

1. Bind a real map and two device records to the frozen C111329 scene, validate original map topology and device readback for each case, and complete the Native controller/capture contract. Resolve the fixed intersection layout against the required between-intersection segment without inventing a new cell.
2. Add per-case config, construction, manifests, finalizers, diagnostic recipes and source-bound positive/negative compatibility/offline/saved-only proofs. Build semantic stage proposals and an independent delivery audit.
3. Review the NRS 484B.290 exception and legal meaning of adjacent intersections/official devices independently from the geometry packet. Do not infer them from record IDs or visual appearance.
4. Rerun the tests and exact strict gate; mark ready only after it passes. Physical motion, actual map site, camera coverage and recordings remain later Native checks once CPU preparation is complete.
