# heldout__C109705__NRS-484B-400-3__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 independent saved-source audit continuation

This section supersedes the exact proof hashes below after correcting the
synthetic diagnostic fixture to isolate comparison phases. The approach variant
changes only approach/entry original body positions and holds departure bodies
fixed. The departure variant changes only departure bodies and holds
approach/entry fixed. `source_comparison_audit.py` independently recomputes
measurements from retained original rows, binds fixed route/config/cameras/trace,
and rejects changed held phases or fixed config. Both synthetic comparisons
pass positive and altered-config negative paths. Diagnostic measured approach
nearest-corner offsets are 0.8 and 1.45 m; destination left-curb distances are
2.807 and 2.926 m. These are software fixture values, not Native observations
or legal cutoffs.

`delivery_audit.py` independently joins source hashes and original frame/body/
trace identities, decodes all four camera streams and composed primary with the
pinned media auditor, and binds the source-decode receipt. Native mode requires
source seal, Native exit, physical completion and an independent original-pixel
review of ego body, approach centerline and destination left curb. All three
marked synthetic positives pass and all three tampered-source negatives fail as
required; their Native-only checks are false.

Current receipts: `exact-proofs.json` SHA-256
`49d15986874d94f51923873488099da10505e642380a665ff642b4bf7195d095`;
`saved-proofs.json` SHA-256
`a1b412c1c0ba2319e30d5178587ced60e23e7bd296ecbcf682acd138860ca255`;
`delivery-audit-proofs.json` SHA-256
`973d09f688de2c740ceacfc34a2c1609638f29e50803595b19b66f9f5e4c4c23`;
`comparison-proofs.json` SHA-256
`f83d296a42b0aa80f79466ffaa7fc99c416a11f71967d2b17330c20af1c4d66e`.
Scoped complete passes; scoped strict rejects truthful **partial** status.
Next CPU work is physical-completion protocol tests, the canonical semantic
proposals and exact execution manifest with audit bindings. A source-backed
Native two-directional/one-way intersection survey must replace the diagnostic
coordinates before a physical capture. No actual turn or legal verdict is
claimed.

## 2026-11-11 exact Native turn construction and saved proof continuation

This section supersedes older "no executable case" statements below.
`turn_native.py` and its exact `runner.py` entrypoint implement CARLA-lazy
source-hashed XODR waypoint verification, a bounded turn feedback controller,
original full-body footprint and phase readback, frame-map and PipelineCapture
sources, four named synchronized RGB streams, world restoration and capture
sealing. `turn_finalizer.py` joins those retained sources through
`turn_source_measurement.py`, generates the selected original-source offset
channel and writes a Native-shaped result without a legal practicability
verdict. The first Native map/route survey in this package is explicitly
synthetic; the runner rejects a loaded map or waypoint position that differs.

`build_turn_construction.py` authors three exact selected cases and three
distinct bounded alternatives per case: shorter lookahead for route drift,
slower turn target for curb overshoot, and raised overview camera for body
occlusion. The current 12 constructions all pass pinned exact `runtime.py
offline` and positive/missing-source `runtime.py compatibility`. Receipts and
hashed logs are in `exact-proofs.json` (SHA-256
`5ad32e34da6360685d79c3e29262f9dfd917e20cd9c206bb50f40c3e6017cda8`).
All three primaries pass exact `runtime.py process-saved` on separately
materialized marked synthetic original attempts, with original bytes preserved
and `missing_evidence=false`; `saved-proofs.json` SHA-256 is
`5e425363490b0b75c8e683b6ad07a0d363e665cc5035c1172a77300211336a1c`.
The current construction and compatibility manifest hashes are respectively
`9887c6c476ce9c0a25f9fa6ff503200b1f6a6cde3b7d3b82e4e8171da23f9252`
and `fb854fd5e7a1bdf5e75f54943d90e0127df98f1f1dd4abe92622f511191cbad9`.

These proofs exercise software paths and synthetic source geometry; the
fixture's static underlying trace is not an actual turn. The source survey
must be replaced with verified Native two-directional/one-way intersection
coordinates before an operator capture. Independent delivery/comparison audits,
the physical protocol, canonical semantic stage proposals and exact execution
handoff still need CPU implementation and proofs. Scoped `worker_check.py
--complete` passes; scoped strict still rejects the truthful **partial** result.
No actual physical or legal acceptance is claimed.

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
