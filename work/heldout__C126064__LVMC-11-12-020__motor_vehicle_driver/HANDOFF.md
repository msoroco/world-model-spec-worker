# heldout__C126064__LVMC-11-12-020__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 authorized marker and original-course continuation

`case-plan.json` now specifies two exact turns, one targeting the indicated
course and one targeting a divergent path, in a comparison that holds the
physical markers, median-opening intersection, vehicle and capture plan fixed.
`marked_course_measurement.py` requires separate source references for municipal
jurisdiction, the intersecting-road geometry and marker authorization; it
rejects markers outside the sourced intersection. It joins every original body
footprint to the frame map and reports centroid/corner distances to the
indicated polyline throughout the turn. No numeric legal disobedience cutoff is
invented.

Two CPU tests pass, including out-of-intersection marker and wrong actor
rejection. Run `.venv-cpu/bin/python -m unittest discover -s
work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`21a8336d6a48f9beff492c4bc9911b0d37a6f2a5c9a4e4626ee959705694cede`.
Scoped complete passes; strict rejects the truthful partial status. Next,
construct a sourced Native median-opening intersection with physical authorized
markers, four-camera capture and the first exact saved finalizer, then run
offline, positive/negative compatibility and saved processing. Physical marker
presence, authorization and any legal outcome are unverified.

## Frozen scope and source

- Law: LVMC 11.12.020 — When authorized markers, buttons, or other indications are placed within an intersection indicating the course to be traveled by vehicles turning thereat, no driver of a vehicle shall disobey the direction of such indications.
- Cell/actor: C126064 / motor_vehicle_driver; layout `median_opening`, maneuver `turn`, control `turn_path_marking`.
- Exact input: `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/assignment.json` (SHA256 `99c4b9c957c0c22c44d5626cbb0c525f30d07157c63e93d8a7509f2172127b83`).
- Witness: `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: dev.regulatory_sign, st.lane_marking, dev.governs, st.intersection, drv.turning, kin.path_length, rel.occupies.

## Required source and construction review

1. A realizable intersection incorporating the median opening, rather than an isolated opening assumed to be an intersection.
2. Any additional signal configuration and its governance.
3. Applicable LVMC jurisdiction.
4. Construct an intersecting-road configuration incorporating the median opening and document its intersection boundaries.
5. Document any additional signal configuration and governance.
6. Establish applicable municipal jurisdiction and driver control.
7. Establish indication authorization, placement within that intersection, indicated course and relationship to the selected turn and median opening.
8. Preserve unresolved definition incorporation and the absence of a numerical disobedience criterion.
9. The authorized marking's course and relationship to ego's turning route and median opening.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C126064__LVMC-11-12-020__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-12 source-hashed Native marker construction checkpoint

`marked_course_native.py` implements CARLA-lazy physical turn-course marker placement from a SHA-256-bound authority record: it requires intersection/median-opening identity, checks that each marker maps to a Native junction, creates each configured marker blueprint, reads back actual x/y placement within 0.05 m and destroys partially spawned markers on failure. Four CPU tests now pass (`cpu-tests.log` SHA-256 `21e5b4282a47f75c7f16c5359a8cb27311fa6e2179003b6588f1f7a79877626b`), including source-tamper, non-junction and readback-mismatch rejection. The authority document in the fake test is a fixture claim, not real municipal authorization. The exact runner must supply a reviewed source file and site/map match, connect the indicated and divergent turn routes to this placement, retain four cameras and original bodies, then run exact offline/compatibility/saved and independent audits. Status remains partial; no physical or legal acceptance is claimed.
