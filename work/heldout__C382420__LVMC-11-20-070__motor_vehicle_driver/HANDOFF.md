# heldout__C382420__LVMC-11-20-070__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: LVMC 11.20.070 — No driver shall enter an intersection or a marked crosswalk unless there is sufficient space on the other side of the intersection or crosswalk to accommodate the vehicle he is operating without obstructing the passage of other vehicles or pedestrians, notwithstanding any traffic-control signal indication to proceed.
- Cell/actor: C382420 / motor_vehicle_driver; layout `intersection`, maneuver `travel`, control `marked_crosswalk`.
- Exact input: `inputs/heldout__C382420__LVMC-11-20-070__motor_vehicle_driver/assignment.json` (SHA256 `8fd739d5c2594831a03f483da5b8406abe72ac37d7f52392f6eb150525282c57`).
- Witness: `inputs/heldout__C382420__LVMC-11-20-070__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: st.intersection, st.lane_enters, st.crosswalk, drv.entering_intersection, rel.surface_gap, kin.extent, drv.following, drv.stopped, dev.traffic_signal, ru.pedestrian, rel.occupies.

## Required source and construction review

1. Actual marked-crossing geometry, intersection boundaries and control governance.
2. Applicable jurisdiction, driver identity and qualifying vehicle.
3. Connected ego and separate participant routes, including any required sidewalks or separate segments.
4. Document intersection and marked-crosswalk boundaries, actual surface markings, control governance and connected participant routes.
5. Establish municipal applicability, driver identity, vehicle scope, dimensions and footprint.
6. Identify the corresponding other side of each entry boundary and record available space, occupied areas and other vehicle or pedestrian passage areas at entry.
7. Other-side space and occupied areas corresponding to each entry boundary.
8. Preserve unresolved state-definition incorporation and autonomous-driver cross-references.
9. Record approach, entry and subsequent motion without defining sufficient space, accommodation or obstruction numerically.
10. Recovered LVMC-11-38-080 remains provisional archived context, not independently confirmed against a current official edition; its actual-trail-ride and enclosed-three-wheel exceptions remain operative, and it is not selected as a target.
11. Retain recovered LVMC-11-38-080 only as provisional archived context, not independently confirmed against a current official edition, with its actual-trail-ride and enclosed-three-wheel exceptions operative. It is not a selected target.
12. Retain signal indications as context; an indication to proceed does not waive the restriction.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C382420__LVMC-11-20-070__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C382420__LVMC-11-20-070__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Entry alternatives and controlled comparisons

`case-plan.json` plans separate marked-crosswalk and intersection entry pairs. Each pair holds a proceed signal and other-road-user route fixed while varying real downstream blocking geometry and measuring free space at the actual entry frame. The signal does not waive the space obligation. Full-vehicle accommodation and actual obstruction of passage must be measured from Native sources; this plan makes no legal cutoff. The intersection alternative requires verification of compatible geometry in the fixed cell. All four cases remain unconstructed CPU work.
