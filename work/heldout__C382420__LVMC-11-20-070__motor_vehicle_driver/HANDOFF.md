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

## 2026-11-12 first exact construction and original-source measurement checkpoint

`space_construction.py` splits the CARLA map's repeated-vertex closed crosswalk polygons, selects one intersecting a connected approach/junction/receiving route, and separately constructs the intersection alternative. CARLA's [Python API reference](https://carla.readthedocs.io/en/0.9.12/python_api/#carla.Map.get_crosswalks) documents repeated first vertices for closed crosswalk polygons. `space_native_runner.py` prepares a standing downstream vehicle in blocked cases, a crossing pedestrian in both arms, original signal readback and four synchronized cameras through `space_camera_capture.py`. Native map/actor capability and resulting visibility remain untested physical facts.

`space_measure.py` computes the first original-body entry frame, measured vehicle extent, contiguous receiving length from original obstacle footprints, and ego overlap with a pedestrian passage polygon. `space_finalizer.py` joins original body, trace and video-frame identities, writes four derived channels from retained raw sources, and makes no sufficiency/obstruction verdict. The current six CPU tests cover clear/blocked space, both entry alternatives, connected marked geometry, source tamper rejection, saved-source joins and exact case selectors (`cpu-measure-tests.log`; SHA256 c060b7ef63bf08789ae085088234977f63aa72a2c0751ae21df0916c2566bb8b).

The first `crosswalk_clear_downstream` inline `construction.json` (SHA256 aa58125220956172771165675b71292df5f29deebc74ff88fdf2c2853577f6df) and root `config.json` materialize successfully through `.venv-cpu/bin/python runtime.py offline --manifest .runtime-work/c382420-stage/probe-manifest.json --case heldout__C382420__LVMC-11-20-070__motor_vehicle_driver__crosswalk_clear_downstream --output .runtime-work/c382420-stage/primary-offline-v2`; the generated diagnostic is under ignored staging. This is an offline import/config/test pass only. It does not establish source-shaped positive/negative compatibility, saved-only processing or Native feasibility. Next CPU work is an internally coherent original-source diagnostic with matched capture/trace/body/video bytes, exact measurement contract and recipe, then its compatibility and saved-only proof before sweeping the remaining three planned cases and fallbacks.
