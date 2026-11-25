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

## 2026-11-24 saved original-source outcome checkpoint

`caravan_saved.py` now analyzes saved original body/frame/context sources and requires 900 frames, caravan forward motion, an actual wide-gap entry transition or narrow-gap nonoccupancy, and no body contact. It keeps the statutory danger judgment unresolved. The production CLI passed on both 900-frame synthetic diagnostic roots; `cases/caravan-saved-wide-diagnostic.json` and `cases/caravan-saved-narrow-diagnostic.json` retain the source hashes and nonacceptance flags. A changed original lane source exits nonzero with `Changed original context source: lane_source` in `cases/caravan-saved-changed-source-negative.log`. Sixteen CPU tests pass. The source fixtures establish software behavior only. Selected constructions, proposals, independent delivery audit, physical preparation and current-runtime strict proofs remain worker-owned; status stays **partial**.

## 2026-11-24 exact inline construction and source measurement checkpoint

Both selected solo-vehicle case IDs now have inline construction bundles in `cases/entrant_can_occupy_gap-construction.json` and `cases/entrant_cannot_occupy_gap-construction.json`, plus one risk-triggered `fallback1` per case. The fallback reduces the shared control speed cap from 4 to 2.5 m/s after original-frame approach-control instability; it does not change the selected gap-width contrast, camera contract or case identity. The diagnostic `FixtureMap` site packets are explicitly unreviewed and cannot start Native capture. An operator-reviewed `C160013_REVIEW_BUNDLE` is required at runtime. `runner.py` is materialized for the pinned Native sealing hash and resolves its exact case from the materialized config. All four primary/fallback bundles passed the official current-runtime `runtime.py offline` command; hashed logs are in `cases/*-offline.log`. The pinned candidate validator accepts both fallback identities and unchanged comparison contracts.

`finalizer.py` now writes original-frame caravan-body, entrant-body, opening, occupancy and contact channels, plus `result.json` and a saved analysis report. `measurement-contract.json` binds three selected requirements to original district/caravan context, continuous body spacing and actual entrant occupancy/contact. The pinned measurement contract validator accepts all three methods for each selected case. Twenty-one CPU tests pass. The independent 900-frame synthetic comparison was regenerated after changing the audit to compare original recorded vehicle types across recordings rather than transient CARLA actor numbers; changed original context sources still fail. The saved wide/narrow diagnostics were regenerated against those source rows.

C160013 remains **partial**. The statute also reaches towing combinations; no physical towing construction exists yet. Current-runtime positive/negative compatibility, Native source delivery audit, physical preparation, semantic proposals, and scoped strict readiness proof remain worker-owned CPU work. No actual Native motion, source-camera pixels, statutory without-danger judgment, or acceptance has been claimed.

## 2026-11-25 pinned physical assessor source checkpoint

`caravan_capture.py` now records each original Native tick's selected rear/front/entrant complete bodies and the entrant lane readback in `participants`, alongside the existing caravan history. `caravan_native.py` writes the assessor-required `caravan_context.json`; the exact wide case requires a reviewed destination lane matching its physical plan. The wide engineering completion is a body-and-lane caravan entry; the narrow engineering completion is approach travel without gap occupancy. Neither defines the statutory without-danger judgment.

`cases/prove_physical.py` exercised the pinned `assess_physical` on 900-frame synthetic wide and narrow source trees: setup, target and maneuver all report `met`; removing original caravan context makes the maneuver `unverified` for each. The receipt and log are `cases/caravan-physical-diagnostic.json` and `cases/caravan-physical-proof.log`. This is a diagnostic of the assessor's source contract, not the required lifecycle or final physical-preparation receipt and not Native evidence. The package suite passes 21 tests, all four refreshed current-runtime primary/fallback offline bundles pass, candidate and measurement contracts validate, and the scoped complete static check passes. C160013 remains **partial**.

The requested unscoped `.venv-cpu/bin/python worker_check.py` completed with exit 1 at `Execution manifest binds another runtime` for retained prior-runtime ready work; it did **not** encounter a binary/Unicode file. Its full traceback is in ignored `.runtime-work/c160013-quick-check.log`. `START_HERE.md` defers prior-ready migration while `PREVIOUS_READINESS.json` exists. The current assignment's scoped complete check passes; its strict readiness gate remains inapplicable while C160013 is partial.
