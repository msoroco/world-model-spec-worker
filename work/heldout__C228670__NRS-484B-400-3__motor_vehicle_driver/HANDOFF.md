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

2026-11-12 return-cap checkpoint: 0 older UTF-8 logs were preserved with full text/path/SHA-256 in `work/_shared/prune-history-2.json`. Restore before scoped strict with `.venv-cpu/bin/python work/_shared/restore_compacted_zero_logs.py --assignment heldout__C228670__NRS-484B-400-3__motor_vehicle_driver`. Status remains partial.

### 2026-11-12 source-bound intersection survey construction

`route_survey.py` now implements a CARLA-lazy prerequisite for the planned two-directional-to-one-way turn. It loads only a SHA-256-bound Native XODR survey, rejects a synthetic-provenance claim, validates named approach/exit road lines and the centerline entry, and checks surveyed driving waypoints against the loaded Native map. It requires an interior Native junction and a distinct exit road. This is construction validation code, not a claim that the generic `road` catalog cell physically contains the required intersection or proves highway directionality. Direction and public-access claims still need original source review; no fixture is promoted to a map survey.

`tests/test_route_survey.py` exercises the fake Native waypoint lookup, missing junction, changed coordinates, off-centerline entry, synthetic-provenance rejection and stale source hash. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C228670__NRS-484B-400-3__motor_vehicle_driver/tests -v` exits 0 (2 tests); `route-survey-tests.log` SHA-256 `a0607745c6a38babcd0d3529a90e251cb6b29bd255689f0ddb8cf11fcd917407`. The assignment-scoped nonstrict complete gate exits 0. Result remains **partial**.

Next CPU construction: bind this survey validator into the first exact runner, capture original route and full-body positions from all four named cameras, implement the source-bound finalizer, then run the primary offline, positive/missing-source compatibility and saved-processing proofs. Carry the same surveyed route into the two controlled variants and their three physical-risk fallbacks each. Add independent delivery/comparison audits and canonical semantic stages. A real Native survey and physical directions remain to be verified during original capture; the missing runner/proof paths are worker-owned CPU work.

`body_position.py` now measures every original body corner against the directed approach centerline and one-way left curb per frame, preserving signed approach offsets, full-body right-of-centerline status and the farthest curb distance. It reports source geometry without a legal cutoff. The four-test `route-survey-tests.log` SHA-256 is `ffaa69e0744e70e3fe5adbfd04714228d8b7390fa80daadc96417dfdf685f8c9`; the test suite checks both turn legs and rejects missing corners, wrong phase and nonfinite source positions. `result.json` binds this current log and keeps status partial. The assignment-scoped nonstrict gate passes. Current return inventory is 10,191 files, below the frozen 10,200 cap. The 35 ready / 16 partial frozen assignment statuses are unchanged; two supplemental partial results also remain in work/.
