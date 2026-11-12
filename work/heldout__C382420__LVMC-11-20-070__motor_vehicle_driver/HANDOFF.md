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

Status is **partial**. The first exact case now has current-source offline, positive/negative compatibility, and saved-only proofs, each using retained original source joins. Its three physically distinct fallbacks pass the staged CPU chain. No physical or legal outcome is asserted. The next CPU work is to construct and prove the remaining crosswalk-blocked and intersection clear/blocked comparisons, bind exact fallback receipts under the return-file cap, complete semantic proposals and independent delivery/comparison audits, then run scoped strict. Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C382420__LVMC-11-20-070__motor_vehicle_driver --complete --require-delivery-ready`.

## Entry alternatives and controlled comparisons

`case-plan.json` plans separate marked-crosswalk and intersection entry pairs. Each pair holds a proceed signal and other-road-user route fixed while varying real downstream blocking geometry and measuring free space at the actual entry frame. The signal does not waive the space obligation. Full-vehicle accommodation and actual obstruction of passage must be measured from Native sources; this plan makes no legal cutoff. The intersection alternative requires verification of compatible geometry in the fixed cell. The first case has a constructed and tested CPU diagnostic; the other three remain planned CPU work.

## 2026-11-12 first exact construction and original-source measurement checkpoint

`space_construction.py` splits the CARLA map's repeated-vertex closed crosswalk polygons, selects one intersecting a connected approach/junction/receiving route, and separately constructs the intersection alternative. CARLA's [Python API reference](https://carla.readthedocs.io/en/0.9.12/python_api/#carla.Map.get_crosswalks) documents repeated first vertices for closed crosswalk polygons. `space_native_runner.py` prepares a standing downstream vehicle in blocked cases, a crossing pedestrian in both arms, original signal readback and four synchronized cameras through `space_camera_capture.py`. Native map/actor capability and resulting visibility remain untested physical facts.

`space_measure.py` computes the first original-body entry frame, measured vehicle extent, contiguous receiving length from original obstacle footprints, and ego overlap with a pedestrian passage polygon. `space_finalizer.py` joins original body, trace and video-frame identities, writes four derived channels from retained raw sources, and makes no sufficiency/obstruction verdict. The current six CPU tests cover clear/blocked space, both entry alternatives, connected marked geometry, source tamper rejection, saved-source joins and exact case selectors (`cpu-measure-tests.log`; SHA256 c060b7ef63bf08789ae085088234977f63aa72a2c0751ae21df0916c2566bb8b).

The current first `crosswalk_clear_downstream` inline construction has SHA256 `7e4cac92d5eb5bf4dd0462611ec126398cfd1f9b0d80ffe04cc56f4c0914ef65`. Exact offline: `.venv-cpu/bin/python runtime.py offline --manifest work/heldout__C382420__LVMC-11-20-070__motor_vehicle_driver/execution-manifest.json --case heldout__C382420__LVMC-11-20-070__motor_vehicle_driver__crosswalk_clear_downstream --output .runtime-work/c382420-stage/primary-offline-current` (exit 0). Exact compatibility with `runtime.py compatibility`, the same work manifest, pinned library and Lean validator passed all positive and missing-source negative checks at `.runtime-work/c382420-stage/primary-compat-current`; `construction_sha256` matches current source. Saved-only processing against the same work manifest passed at `.runtime-work/c382420-stage/primary-saved-output-current`, joining nine original frames and preserving original hashes. The diagnostic is synthetic and does not establish Native feasibility or legal sufficiency.

Three fallback constructions change exactly one physical knob each: route sampling `route_step_m=1.5` for connected route/crosswalk risk; ego throttle `0.27` for failure to reach entry during capture; overview height delta `0.7 m` for entry/participant visibility risk. Each passed staged exact offline, positive/negative compatibility and saved-only processing with unchanged source originals at `.runtime-work/c382420-stage/fallback{1,2,3}-*`. Their construction files and receipts are still in ignored staging pending returned bindings and file-cap margin. Current six tests pass; `cpu-measure-tests.log` SHA256 `3bcfc5a22a8a07703ec78f18286f30b0929197533f5deae2e8daaac24f9133f2`.

Next, complete the three other exact cases and comparisons, prove each primary and three distinct fallbacks, bind canonical semantic stages, measurement contracts and source-joined independent audits. Keep status partial until scoped strict passes. No CARLA/GPU command was executed.

## 2026-11-12 blocked-crosswalk exact comparison checkpoint

The `crosswalk_blocked_downstream` primary and three distinct physical-risk fallbacks now pass staged offline, positive/negative compatibility and saved-only processing. The primary compatibility receipt is `.runtime-work/c382420-stage/blocked-compat-v2/compatibility.json`; saved receipts and source-preservation checks are under `.runtime-work/c382420-stage/blocked-primary-saved-output-current` and `blocked-fallback{1,2,3}-saved-output-current`. The blocked diagnostic and source-hashed recipe are returned; construction, contract, manifest bindings and proof receipts remain in ignored staging while the shared return cap is managed.

The independent source-bound comparison script `.runtime-work/c382420-stage/audit_crosswalk_pair.py` passed and wrote `crosswalk-pair-audit.json`. It requires byte-equivalent ego original footprints/times, entry geometry, signal readback, participant passage and four source-camera data, and allows only the standing downstream vehicle footprint to differ. Both entries occur at frame 2 with proceed signal. The synthetic measured contiguous receiving length changes from 16.0 m (clear) to 3.0 m (standing blocker at 3–8 m). These are diagnostic observations, not a legal sufficiency finding or Native physical acceptance. The intersection alternatives and canonical return bindings still need worker-owned CPU work.

## 2026-11-12 intersection pair staged CPU proof checkpoint

Both exact intersection primaries and each of their three distinct physical-risk fallback constructions pass offline, positive/negative compatibility and saved-only processing. Current staged manifests, constructions, receipts and original-source fixtures are under `.runtime-work/c382420-stage/intersection_{clear,blocked}_downstream-*`; their two source-hashed diagnostic generators/recipes are returned under this assignment. Each saved receipt preserves original hashes, joins nine frames, and disclaims physical and legal acceptance. The independent source-bound comparison script `audit_intersection_pair.py` passes: original ego frames, junction entry geometry, signal, participant passage and four camera sources are fixed; only the standing downstream vehicle differs. Synthetic measured receiving length changes from 14.0 m to 3.0 m at frame 2 with proceed signal.

All four planned exact case primaries and all twelve distinct physical-risk fallbacks now have staged offline, positive/negative compatibility and saved-only CPU passes. These proof artifacts still require canonical return bindings and manifest/contract wiring. Canonical semantic proposals, delivery audit and scoped strict remain incomplete CPU work; status stays partial. Actual junction and marked-crosswalk feasibility, signal governance, pedestrian route and visual coverage remain Native physical checks.
