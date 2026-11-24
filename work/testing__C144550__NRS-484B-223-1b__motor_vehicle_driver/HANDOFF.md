# C144550 CPU handoff — NRS 484B.223(1)(b)

Status: **partial**. The fixed cell is one-way multilane/change_lane/lane_marking. The exact law requires an appropriate turn signal and ascertainment of safety before moving from a clearly marked lane where two or more same-direction lanes exist. It provides no numeric signal lead time or safe gap. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps early, late and wrong-direction signals, a measured closer target-lane vehicle, and a rightward comparison. `native_lane_construction.py` uses actual Native adjacent-lane and marking queries in both directions. `lane_change_measurements.py` joins original frames to complete ego and target bodies, source-lane polygon, indicator state and target-lane longitudinal gaps. It reports signal timing and whether the indicator is active at first body departure. It does not infer the driver's safety ascertainment or a legal minimum gap. Three CPU tests pass in `cpu-tests.log`, including left/right Native selection, early/late signal timing, missing target inventory and stale-frame rejection.

Next CPU work: source an actual two-or-more clearly marked same-direction lane roadway, construct both lane-change routes and Native signal/controller calls, capture all four raw cameras plus original actor/lane/lamp evidence, and implement saved finalizer/measurement contract. Add three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual markings, signal visibility, target traffic and motion remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C144550__NRS-484B-223-1b__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C157964__NRS-484B-257-1__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## 2026-11-23 same-direction Native lane guard

The Native adjacent-lane selector now rejects lane ID zero and a neighbor with the opposite CARLA lane-ID sign, even if its road ID and marking match. This prevents a centerline crossing from being used as the same-direction lane-change target. The existing right-lane test now uses a same-sign lane and explicitly rejects an opposite-sign neighbor. Three CPU tests and the scoped nonready complete check pass; `cpu-tests.log` retains SHA256 `52faaa32758331b884a115ebdeecf56a6b90db64546678f6e950c842e7d32bc5`. C144550 remains **partial** while the controller, exact saved path, fallbacks, proofs and actual marked-lane observations are unfinished. No Native or legal acceptance is claimed.

## 2026-11-23 exact-case Native indicator component

`native_lane_construction.py` now maps all five exact case IDs to planned indicator commands. The late-signal case remains off until an original body-departure observation is supplied; the wrong-direction and rightward cases command the right indicator. `apply_indicator` clears only turn-lamp bits, preserves other Native lights and returns a light-state readback. This controls a planned signal but does not prove camera-visible display or legal signaling; `lane_change_measurements.py` remains the original-frame check. `case-plan.json.native_indicator_policy_cpu_component` binds the source and test hashes. Four CPU tests passed (`cpu-tests.log` SHA256 `4404ea6c23f3c3c12be79309057a055afb3cdbf15390ac58f855143c6edfbd23`), as did pinned `runtime.py preflight` and the scoped nonready complete check. This is a controller component; exact runner integration and saved processing remain unfinished. C144550 remains **partial**.

## 2026-11-23 exact-case Native lane-change control step

`native_lane_construction.py` now issues a bounded forward Native control step toward the previously verified adjacent marked-lane waypoint. It checks the exact selected case against the lane direction, calculates signed heading error and steering toward that lane, reads Native velocity, commands throttle/brake within a bounded target speed, applies the case-specific turn signal without clearing other lights, and returns the Native lamp readback. The CPU test drives left and right fake Native routes, verifies steering signs, readback, forward control, late-signal timing and exact-case direction rejection. This is a controller component; original body, marking, lamp, target traffic and safety ascertainment remain source measurements.

All five package tests pass (`cpu-tests.log` SHA256 `2139ec77a4a9e65448e72447403c7a381b473c44a3a79c39354fa5476eeb7ced`); source SHA256 `d4039fb0d4998d4600194c6e3c9ae3337e9ab6c48307a8cd246416fcbbeda13d`. The case plan and result test hash are rebound. Pinned CPU preflight and scoped nonready complete check pass. C144550 remains **partial** pending exact runner, four-camera saved path, fallbacks, comparison and delivery proofs. No Native capture or legal/physical acceptance is claimed.

## 2026-11-23 original lane inventory and Native capture core

`lane_change_measurements.py` now verifies the claimed same-direction marked-lane count against an explicit original lane inventory. It rejects duplicate or missing source/target IDs, differing road IDs, opposing heading vectors, missing marking sources and opposite Native lane-ID signs. The source SHA256 is `2fb82fa111c55237805bfe73a546e58fcbfa119c18f56960e2a37d337b5c387b`.

`native_lane_construction.py` now also has a 900-frame capture core that ticks the exact selected case, joins each original lane observation to Native frame/time, retains requested indicator and lamp readback, joins all four named original cameras, and closes every writer on success or failure. CPU fakes verify 900 joined frames, late-signal ordering, camera count and a skipped-camera rejection. This is a reusable runner core; camera sensor creation, source file persistence, site review and saved finalization still require construction. Source SHA256 `bb43c797887352717e69fc85b836f57c4aa665f649e7decc59d9f12f4da26fc7`.

Seven package tests pass (`cpu-tests.log` SHA256 `236e435fb6addfb89a7c6b2a49a850593bb20270b1e530fa68230fb02ea4c785`), as do pinned CPU preflight and scoped nonready complete check. The case plan and result test hash are rebound. C144550 remains **partial**; no Native capture, physical acceptance or legal safety ascertainment is claimed.

## 2026-11-23 source persistence and saved finalizer

`lane_change_measurements.py` persists original lane context, Native lane rows and a frame map without overwriting prior sources. It validates the saved rows and rolls back invalid new source sets. Its exact saved finalizer requires the full 900 original frames, all four named camera files, config and trace, then emits three source-derived observation channels, a native result and an analysis report. The native result passes through the pinned physical checker. The finalizer binds its lane-transition descriptor to the sourced target lane and rejects missing original ego lane readback. Signal pattern mismatch and target-body longitudinal gap remain observations; driver safety ascertainment and legal conclusion remain unresolved. Raw camera decoding and physical acceptance are separate.

Thirteen CPU tests pass, including a 900-frame synthetic source fixture run through the command-line finalizer and pinned physical checker. That fixture uses placeholder camera files, so it does not prove media decoding, original pixels, Native behavior or full `runtime.py process-saved`. Measurement/finalizer source SHA256: `be9bde10955daf002048391ae7ce92f916b22dac41d4e9f38e489a9ac709a8bd`; test log SHA256: `30e3c6058458a34f5d910acc141868111e5d3191544731a2f4d80765795d9191`. Pinned CPU preflight and scoped nonready complete check pass. The case plan binds the current source and test log. C144550 remains **partial** pending actual Native site context, raw camera acquisition, exact runner integration, complete valid-media saved-processing proof, fallbacks, semantic proposals and independent audits. No Native, physical or legal acceptance is claimed.
