# heldout__C109705__NRS-484B-400-3__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 original-source measurement continuation

`turn_source_measurement.py` now joins a named original road-geometry packet,
every measured body footprint and the original frame map. It requires source
identity, a two-directional approach, one-way departure, left-turn maneuver,
public non-alley intersection, matching actor and frame/time identities, and
ordered approach, entry and departure intervals. It preserves original body
corner offsets from the directed centerline and distances to the directed
left curb, plus source hashes. These are descriptive measurements; no
statutory lateral threshold or practicability decision is inferred.

Four CPU tests pass, including wrong destination direction, omitted departure
interval and actor-identity rejection. Command:
`.venv-cpu/bin/python -m unittest discover -s work/heldout__C109705__NRS-484B-400-3__motor_vehicle_driver/tests -v`.
`cpu-tests.log` SHA-256 is
`844ab3a77e1ce1c9bc2413a45a2d7a79ba6b4b8a54caf4f2d6e04596a14d7a56`.
The scoped complete checkpoint passes; scoped strict still fails because status
is correctly **partial**. Next, connect this helper to a CARLA-lazy Native
runner and four-source capture, finalize the first reference case from retained
sources, and prove exact offline, positive/negative compatibility and saved
processing before expanding comparisons and fallbacks. No Native turn or
physical/legal acceptance is claimed.

## Frozen scope and source

- Law: NRS 484B.400(3) — If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn from a two-directional highway onto a one-way highway, the approach for the left turn must be made in that portion of the right half of the highway nearest the centerline thereof, and the turn must be made by turning from the right of the centerline where it enters the intersection as close as practicable to the left-hand curb of the one-way highway.
- Cell/actor: C109705 / motor_vehicle_driver; layout `intersection`, maneuver `left_turn`, control `centerline`.
- Exact input: `inputs/heldout__C109705__NRS-484B-400-3__motor_vehicle_driver/assignment.json` (SHA256 `07229e57184216303557d097429a18b4074132d55363065f607092b8b90b11e5`).
- Witness: `inputs/heldout__C109705__NRS-484B-400-3__motor_vehicle_driver/witnesses.json`, source index 425; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.turning, st.centre_line, rel.occupies, st.one_way_roadway, st.road_edge, kin.position, st.intersection, st.lane_enters, st.lane_direction.

## Required source and construction review

1. Construct an undivided two-directional approach and one-way receiving highway.
2. Construct the required road directions; identify approach right half, centerline entry point and destination left-hand curb.
3. Establish actual physical control of an included vehicle, intended left turn, public-highway status and qualifying non-alley intersection.
4. Establish subject and highway scope, intersection boundaries and physical practicability circumstances.
5. Identify the right half, nearest-centerline portion and destination left-hand curb.
6. Place the centerline on the approach and identify where it enters the intersection.
7. Retain approach, turn origin and curb relationship throughout the turn, including physical circumstances bearing on practicability, without interpreting the standard or imposing legal cutoffs.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C109705__NRS-484B-400-3__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C109705__NRS-484B-400-3__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Controlled left-turn comparisons

`case-plan.json` plans a shared reference case plus separate approach and departure variants. `approach_position` changes only measured approach body position within the right half near the centerline; `departure_position` changes only measured departure body position near the one-way left curb. Both hold connected two-directional approach, one-way departure, left-turn maneuver, cameras and duration fixed. The exact law gives no lateral cutoff. All cases are planned only; construction, source-bound measurements, fallbacks, compatibility and saved audits remain CPU work.

## 2026-11-11 geometry continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` passes with the updated
CPU environment, FFmpeg and Lean. `turn_geometry.py` implements descriptive
body-corner offsets from a directed two-directional approach centerline and
distances from the destination one-way highway's left curb, with the surveyed
intersection-entry point required on the centerline. Negative approach offsets
are on the right half when the line points into the intersection. The helper
does not decide which portion is legally nearest or what is practicable; those
remain contextual review questions. Two CPU tests exercise a right-half body,
a crossing body, rotated directions and invalid geometry. Run
`.venv-cpu/bin/python -m unittest discover -s
work/heldout__C109705__NRS-484B-400-3__motor_vehicle_driver/tests -v`;
`cpu-tests.log` and its SHA256 are recorded in `result.json`.

Next CPU work: retain the surveyed centerline, destination curb, roadway
directions, intersection entry and original body corners from Native source
frames; build the selected reference case through exact runner, four-camera
source capture, finalizer, offline and positive/negative compatibility and
saved-processing proofs. Then realize the isolated approach and departure
comparisons, fallback constructions, semantic proposals and independent
audits. The geometry test is a software fixture and proves no actual turn.

Latest scoped strict gate log `strict-gate.log` SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`; exit code 1 because status is correctly partial.
