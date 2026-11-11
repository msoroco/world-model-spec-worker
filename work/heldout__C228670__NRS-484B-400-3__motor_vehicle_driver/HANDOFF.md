# heldout__C228670__NRS-484B-400-3__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.400(3) — If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a two-directional highway onto a one-way highway, the approach for the left turn must be made in that portion of the right half of the highway nearest the centerline thereof, and the turn must be made by turning from the right of the centerline where it enters the intersection as close as practicable to the left-hand curb of the one-way highway.
- Cell/actor: C228670 / motor_vehicle_driver; layout `road`, maneuver `left_turn`, control `centerline`.
- Exact input: `inputs/heldout__C228670__NRS-484B-400-3__motor_vehicle_driver/assignment.json` (SHA256 `07292f25767eb2beba740317e07cf852a96a888818ffcf0b9424f0d1165bf30e`).
- Witness: `inputs/heldout__C228670__NRS-484B-400-3__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.turning, st.centre_line, rel.occupies, st.one_way_roadway, st.road_edge, kin.position, st.intersection, st.lane_enters, st.lane_direction.

## Required source and construction review

1. Establish approach and destination permitted directions, undivided approach configuration, approach right half, centerline and the point where that centerline enters the intersection.
2. Establish driver, vehicle, highway dedication and public-access facts.
3. Establish road directions, turn destination and centerline placement on an undivided two-directional approach to a one-way highway.
4. Identify the physically controlling driver and included vehicle; establish intended left turn, highway dedication, public access and qualifying non-alley intersection.
5. Identify the qualifying intersection, centerline entry point, approach right half and destination left-hand curb.
6. Preserve unresolved meanings of one-way operation and 'as close as practicable'; do not infer a no-passing zone or required centerline crossing.
7. Retain physical circumstances relevant to practicability; do not infer a no-passing zone or required crossing from centerline presence.
8. Retain trajectory and destination left-hand-curb geometry throughout the turn, with obstacles, vehicle geometry and other physical circumstances bearing on practicability.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C228670__NRS-484B-400-3__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C228670__NRS-484B-400-3__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Controlled left-turn comparisons

`case-plan.json` plans a shared reference case plus separate approach and departure variants. `approach_position` changes only measured approach body position within the right half near the centerline; `departure_position` changes only measured departure body position near the one-way left curb. Both hold connected two-directional approach, one-way departure, left-turn maneuver, cameras and duration fixed. The exact law gives no lateral cutoff. All cases are planned only; construction, source-bound measurements, fallbacks, compatibility and saved audits remain CPU work.
The frozen cell layout is `road`, so intersection compatibility is unverified. Inspect native map geometry and candidate cells before claiming this branch runnable.
