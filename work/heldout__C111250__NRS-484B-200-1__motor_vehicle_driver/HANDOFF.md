# Handoff: heldout__C111250__NRS-484B-200-1__motor_vehicle_driver

## Frozen scope

Upon all highways of sufficient width a vehicle must be driven upon the right half of the highway, except as follows: (a) When overtaking and passing another vehicle proceeding in the same direction under the laws governing such movements; (b) When the right half of the highway is closed to traffic; (c) Upon a highway divided into three lanes for traffic under the laws applicable thereon; (d) Upon a highway designated and posted for one-way traffic; or (e) When the highway is not of sufficient width.

Cell C111250: intersection / travel / centerline; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Baseline sufficient-width highway right-half travel, with measured right/left body position.
- Exception (a): lawful overtaking and passing same-direction vehicle.
- Exception (b): right half closed to traffic.
- Exception (c): three lanes for traffic under applicable law.
- Exception (d): designated and posted one-way highway.
- Exception (e): highway not of sufficient width.
- No numeric legal cutoff for sufficient width is specified.

## Current checkpoint

Twelve planned cases cover right/left body position for the base rule and each of the five textual exceptions: same-direction overtaking, right-half closure, three lanes, posted one-way and insufficient width. `road_half.py` requests physical road variants, a closure, a one-way sign or a passing vehicle through an adapter; it measures original four-corner body position relative to the road centerline. Eleven controlled comparisons isolate side or exception premise. Tests exercise feature creation and source/fixed-condition rejection; `cpu-tests.log` SHA256 is `671fdcdc279307adebfdeadaae4812ab2a16f6bb5b78fc19a79b988c12f585c2`. None of these engineered positions decides legal exception applicability.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111250__NRS-484B-200-1__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111250__NRS-484B-200-1__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C111250__NRS-484B-200-1__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## 2026-11-15 source-bound Native adapter and audit checkpoint

`road_half.py` now contains a CARLA-lazy `NativeRoadHalfAdapter` that surveys the loaded road with `get_waypoint_xodr`, traverses adjacent driving lanes, checks road width and one-way direction requests, spawns subject/passed vehicles and physical closure/sign assets, and provides reverse-order actor cleanup. It rejects missing lanes/assets and a one-way asset whose blueprint identity does not identify a one-way sign. Its `measure_saved` reads original road geometry, exception context, four-corner body history and frame map, checks road/feature source hashes and identity/time joins, and measures each frame's complete body side with road orientation. `delivery_audit.py` independently full-decodes all four saved cameras, checks their original frame joins, and runs a source-based two-case body-side comparison. These are software preparations; the CPU fakes and black synthetic frames do not verify realized Native layout, sign meaning, visibility, lawful passing, sufficient width or legal outcome.

Proof: `.venv-cpu/bin/python runtime.py preflight` exited 0. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111250__NRS-484B-200-1__motor_vehicle_driver/tests -v` exited 0, seven tests, `cpu-tests.log` SHA-256 `19919f9587a2838537ab23688ab3539564ea8b763a017b557c821e9f43fa2897`. Tests cover fake Native lane/asset creation, both body-side lanes, overtaking and closure actor creation, saved road/feature source hash and frame negatives, direction reversal, independent four-camera full decode and missing-camera rejection. The scoped nonstrict `worker_check.py --assignment heldout__C111250__NRS-484B-200-1__motor_vehicle_driver --complete` exits 0. Its scoped strict `--require-delivery-ready` exits 1 at `preparation.py:276` because this assignment remains correctly partial.

Next CPU action: materialize one primary exact `none_right` construction with config, runner, four-camera Native capture, retained original road/exception/body/frame and feature source files, and a saved finalizer that emits named measurements from those originals. Run pinned `runtime.py offline`, positive/missing-source `runtime.py compatibility` and fresh `runtime.py process-saved` for it before expanding all 12 planned exact cases, risk-triggered fallback bundles, lifecycle/physical proofs and canonical semantic proposals. Bind the independent audits to exact manifest cases and rerun their negative probes. The temporary file cap is 10,200 returned files; coordinate proof-preserving compaction before adding the many required bundle/proof files. This is a capacity management issue for ongoing worker-owned work, not a delivery blocker.

## 2026-11-16 first exact primary and saved processing checkpoint

The first `__none_right` primary is now a source-bound exact construction. `runner.py` and `road_half.py` request loaded Native road geometry and a right-half vehicle path, capture four synchronized camera streams and original road, exception, body-corner, trace and frame records, and close/restore owned resources. `finalizer.py` derives the named full-body side, left-half presence and exception-source channels from originals; `diagnostic.json` is explicitly synthetic software scaffolding. The 12-case plan and draft `proposals/cases.json` now cover the baseline plus all five textual exceptions, with six selected requirement dispositions. They do not decide legal applicability.

Pinned exact `runtime.py offline` passed for the first primary with `simulation_started: false` (`first-primary-offline.log` SHA-256 `de4f0a599273916ed38dce3c05581a33a1445595ee1fdf3e12aec18d9d30913f`). Pinned positive/missing-body-original `runtime.py compatibility` passed, including selected analysis, Lean conversion and full four-camera decode (`first-primary-compatibility.json` SHA-256 `c484a658a013a89cc3b244b3aa458947b7a759db3ae2f3b7e50250112be41bf9`; missing-original log SHA-256 `ef6973c8103f1db78c51b522105ea251a3b4ad486f0a1f05bef2922ca986eb82`). Static `check_receipts` returns true. Fresh `runtime.py process-saved` on a newly materialized diagnostic attempt passed with nine source-joined frames, preserved originals, final video decode and no physical/legal acceptance claim (`first-primary-saved-processing.json` SHA-256 `112f0a89cf7e380b361d640e3ba1d3dfb15ca3c08ce23b52899f2c938b109ef7`). These records are bound to `provisional-manifest.json`; first construction SHA-256 is `d21e84b2655dc60ba3873cad9d18b778dc253ac8ce1c2a4bda4bd4c1b330c6e0`. Scoped nonstrict `worker_check.py --complete` passes.

Status remains **partial**. Next worker-owned CPU work: build `__none_left` and the ten exception-side exact cases with source-specific Native premises, each with three distinct risk-triggered fallback constructions; run offline, positive/missing-source compatibility and fresh saved processing for all selected candidates; implement exact-case independent delivery/comparison negatives, physical/lifecycle receipts and canonical semantic stages. Rerun scoped strict only after the complete case set and all CPU proofs are bound. The synthetic proof does not establish actual Native geometry, camera visibility, passing legality, roadway width legal sufficiency or any legal outcome.
