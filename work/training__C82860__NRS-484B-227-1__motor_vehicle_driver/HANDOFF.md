# training__C82860__NRS-484B-227-1__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.227(1): Every vehicle driven upon a divided highway must be driven only upon the right-hand roadway and must not be driven over, across or within any dividing space, barrier or section or make any left turn, semicircular turn or U-turn, except through an opening in the barrier or dividing section or space or at a crossover or intersection established by a public authority.

Cell: divided_road / u_turn / median_barrier; actor: motor_vehicle_driver. Frozen witness count: 2. Membership rows: {'demo-train': 2, 'full-train': 2}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

divided highway; same U-turn intent; genuine barrier and public-authority-established opening/crossover Vary only `median_crossing_location` (category) across ['authorized_opening', 'barrier_crossing']. Record native median geometry, barrier gap, crossing footprint, road direction and opening authority. The definitions are not selected recordings, and requested settings are not measured results.

## New CPU construction and proof

`native/road_request.py` now authors the exact two-direction OpenDRIVE road, two physical median barrier sections with a six-meter opening, and two distinct 600-frame/four-camera U-turn route requests. The opening request crosses at x=0 through the gap; the barrier request crosses at x=10 in a dividing section. Both begin on the eastbound right-hand roadway at the authored driving-lane center y=-6.75 and target the westbound driving-lane center y=6.75. The two-case checker rejects a changed camera or map request. `PYTHONDONTWRITEBYTECODE=1 TMPDIR=.runtime-work .venv-cpu/bin/python -m unittest discover -s work/training__C82860__NRS-484B-227-1__motor_vehicle_driver/native -p 'test_road_request.py' -v` passed two tests. `native/runner.py` adds a prospective synchronous Native acquisition path with authored-map and original two-direction roadway readback, two median objects, body vertices, four joined camera streams, sealed capture, and world cleanup. Its `--check` passes on both exact materialized request bundles under `.runtime-work/c82860-lead/`; this is a static CPU check, not a CARLA execution. These requests are not yet selected delivery constructions; Native physical motion and camera capture remain unverified. The public-authority establishment field remains pending original source review, including for the geometric opening.

`analysis/branch-expansion.json` quotes eight separate source branches: right-hand roadway, dividing space, left turn, semicircular turn, U-turn, opening, crossover and public-authority intersection. The existing opening versus barrier U-turn pair is preserved. Added branches remain unselected pending accepted-evidence and catalog review; a physical gap alone is not public authorization.

`analysis/divided_road.py` measures original-shaped full vehicle footprints against convex surveyed median, opening and both roadway polygons. It retains overlap counts and requires 20 Hz timing and four source-camera frame joins; it checks for an authority source reference but explicitly outputs `authority_verified: false` and an unresolved legal judgment. `analysis/test_divided_road.py` passes two 600-frame, 30-second `synthetic_native_sample` crossings: one through the opening and one over the median outside it. Six negative probes reject missing camera, median geometry, authority reference, footprint, timing and duration. Log SHA-256: `b8b3564e2c4fdf6d4b196c42e67a20bed686bd3835fecf6be4a17c0e44fd8c81`. Synthetic geometry and motion do not establish original Native conditions.

The assignment-scoped checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C82860__NRS-484B-227-1__motor_vehicle_driver --complete` passes static checks. The strict ready gate has not passed.

## Remaining CPU work

Review the two accepted recordings with source hashes before new capture selection. Verify public-authority opening/crossover/intersection evidence and cell compatibility for each uncovered alternative. Bind the authored road requests and static runner into exact selected Native bundles; build canonical semantic stages, risk-based candidate fallbacks, source-bound saved finalization, positive/negative compatibility, and independent delivery and comparison audits. Run the scoped strict gate before any ready label. Original physical footprints, map geometry and camera pixels require later source review; legal outcomes remain unknown.
