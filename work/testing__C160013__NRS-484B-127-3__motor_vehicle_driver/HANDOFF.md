# C160013 CPU handoff — NRS 484B.127(3)

Status: **partial**. Fixed cell: highway outside business district, following in a motor-vehicle caravan. The law requires space between vehicles so another vehicle or combination can enter and occupy without danger; it gives no numeric gap. Frozen accepted-evidence inventory is empty.

`caravan_construction.py` calls Native `world.try_spawn_actor` for at least three distinct participants, checks initial separation and cleans up. `caravan_spacing.py` joins original frames to complete body positions, source-backed highway/district/caravan context and inter-body clearances, plus the entering vehicle's body. Three CPU tests pass for wide/narrow gaps, missing district activation, stale frame and real Native spawn cleanup. The measurements do not decide danger.

Next CPU work: source district and caravan status; construct controlled gap entry/occupancy and separate towing variant if selected coverage requires it. Implement exact runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual motion and danger remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C215286__NRS-484B-113-2__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## 2026-11-24 source-bound caravan entry construction checkpoint

`caravan_spacing.py` now requires original UTF-8 district, caravan membership, route and lane files with exact SHA-256 bindings. It rejects a changed source, changing member or entrant IDs, broken 20 Hz frame cadence, a member reversing against the sourced highway direction, and contact falsely counted as gap occupancy. It records complete entrant-body containment between adjacent original caravan bodies, a frame-observed entry transition, and caravan forward motion. `caravan_entry.py` constructs a bounded lateral merge waypoint into a source-shaped wide gap, or a stop-before waypoint for the narrow-gap case; it rejects an entrant that cannot physically fit the proposed wide-gap opening. Eight CPU tests pass, and `.venv-cpu/bin/python worker_check.py --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --complete` passes. These fixtures are synthetic structural checks and do not establish a legal danger threshold.

C160013 remains **partial**. Next CPU work is the exact source-reviewed Native multi-vehicle runner, continuous entrant and caravan controls, four synchronized raw cameras, saved finalization, selected-case constructions and justified fallbacks, canonical semantic proposals, independent delivery/comparison audits and current-runtime offline, compatibility, saved-source, physical and scoped strict proofs. Actual Native motion and the statutory danger judgment remain later local checks.

## 2026-11-24 independent full-duration comparison checkpoint

`caravan_comparison.py` independently re-analyzes both original source trees. It fixes map, highway, road, district/caravan activation, source hashes and actor identities; rejects body contact and a nearby vehicle in another lane being counted as occupancy; requires a frame-observed wide-gap entry, no narrow-gap occupancy and a genuinely larger physical opening. `cases/prove_comparison.py` generated two 900-frame, 20 Hz synthetic source trees under ignored `.runtime-work/` and ran the production CLI positive and a changed-original-lane-source negative. `cases/caravan-comparison-diagnostic.json` records 900 frames per case, 8 m versus 1 m opening, wide entry observed, narrow occupancy absent, physical acceptance false and legal danger judgment unresolved. The negative exits 1 for changed original context sources. Ten package tests pass and the assignment-scoped complete static checker passes. No Native motion was observed.

The remaining worker-owned CPU work is still the exact Native runner/controller and four-camera capture, source-reviewed site packet, saved finalization, selected constructions and fallbacks, semantic proposals, independent delivery audit and current-runtime package proofs. C160013 remains **partial**; a synthetic comparison cannot make it delivery ready.

## 2026-11-24 bounded Native control checkpoint

`caravan_spacing.py` now requires the entrant's complete body to lie longitudinally between the adjacent members **and** laterally inside their lane before reporting gap occupancy; an adjacent-lane vehicle is rejected as a false positive. The independent comparison audit rejects any body contact in either selected case. `caravan_control.py` computes bounded forward throttle, brake and steering from original position, yaw, speed and waypoint, brakes at the waypoint or for a configurable engineering body-clearance guard, and lazily applies a Native `VehicleControl` with reverse disabled. These controls are not a legal danger threshold. Eleven package tests pass and the assignment-scoped complete static checker exits 0. The 900-frame positive/changed-source comparison proof remains valid and synthetic.

C160013 remains **partial**. The next worker-owned CPU step is to bind `caravan_entry.py` and `caravan_control.py` into an exact CARLA-lazy runner with source-reviewed Native site packet and synchronized four-camera capture, then build selected constructions, fallbacks, saved processing, semantic proposals and independent delivery proofs before a scoped strict gate. Real physical movement, camera views and the law's danger judgment remain local checks.


## 2026-11-24 source-bound Native capture implementation checkpoint

`caravan_capture.py` now validates a reviewed Native map/district/highway/caravan packet and four original UTF-8 source hashes. It drives three distinct caravan members and a distinct entrant from the bounded control and entry plan, joins four raw cameras to each original Native frame, saves complete vehicle bodies and a 20 Hz frame map, and leaves actual occupancy and legal danger unresolved. `caravan_native.py` installs an operator-reviewed packet into a materialized attempt, rejects source/output path collisions, checks each participant's actual Native road, calls the shared `PipelineCapture` for each tick, restores world settings and seals only a clean full capture. `caravan_cameras.py` and `caravan_video.py` provide four source sensors and lossless FFV1 writers. The operator must supply an original reviewed bundle; the fake review files in tests are structural diagnostics only.

Fifteen assignment CPU tests pass, including a two-frame fake-world join, four Native sensor creation and cleanup calls, and a changed original source rejection. `.venv-cpu/bin/python worker_check.py --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --complete` passes. The two selected cases still need materialized exact construction JSON, justified fallback bundles, source-bound saved finalization, semantic proposals, delivery audit and current-runtime offline/compatibility/physical/scoped strict proofs. C160013 remains **partial**; no Native motion or legal danger determination was observed.

The scoped strict gate was attempted and exits 1 with `Preparation acceptance failed: partial/missing packages remain`, consistent with `result.json` remaining partial. Its log is `scoped-strict.log`.
