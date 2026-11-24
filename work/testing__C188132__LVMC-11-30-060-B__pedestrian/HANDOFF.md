# testing__C188132__LVMC-11-30-060-B__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.060(B); with 11.30.060(C) — Any pedestrian crossing a roadway at a point where a pedestrian tunnel or overhead pedestrian crossing has been provided shall yield the right-of-way to all vehicles upon the roadway. The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.
Assigned branch(es): Pedestrian roadway crossing at a provided overhead crossing..
Cell: C188132 (pedestrian_overpass, cross_road, other_vehicle); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C188132__LVMC-11-30-060-B__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and source-audit checkpoint

The exact source-hashed engineering map `candidate-overpass.xodr` contains a surface vehicular roadway at z=0 m and a crossing elevated sidewalk deck at z=5 m. It is a candidate, not proof of a provided usable overhead crossing: access ramps/stairs, Native bridge rendering, original pixels and municipal classification remain unverified. The frozen accepted inventory has zero recordings. The municipal text requires yielding to all vehicles upon the roadway when crossing at a point with an overhead crossing or tunnel; the designated-place prohibition exception is retained. This fixed cell is an overpass, so the tunnel alternative needs a separate compatible cell review by the lead.

`scene-yield_before_vehicle.json`, `scene-enter_ahead_of_vehicle.json` and `scene-designated_prohibition.json` are exact 20 Hz, 900-frame plans. `entry_timing` holds map, route, speeds and prohibition context fixed while changing only the pedestrian hold request. `designated_exception` holds the controller and physical plan fixed while changing only the authored prohibition context. The latter is a source-context probe for LVMC 11.30.070(B), not a legal conclusion. Every scene records the same physical risk: Native structural access and visibility may fail; there is no tested fallback yet.

`runner.py --check` validates each scene against the actual source map without CARLA. `overpass_source.py` implements lazy original walker/vehicle spawning and controls, 900-frame original position/timing measurement, hash-verified saved source audit and independent pair audit. `native_capture.py` and `walker_pipeline_capture.py` provide four synchronized camera acquisition and original walker graph collection for the candidate Native runner. The nine focused tests exercise both participant spawn calls, control timing, elevated map rejection, complete histories, missing/stale evidence and both pair audits, including fixed vehicle trajectory rejection. Tests use fake actors and textual source histories, so they establish software behavior only.

Reproduce: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=work/testing__C188132__LVMC-11-30-060-B__pedestrian .venv-cpu/bin/python -m unittest discover -s work/testing__C188132__LVMC-11-30-060-B__pedestrian/tests -v` (see `cpu-tests.log` and `result.json` SHA). Run `.venv-cpu/bin/python work/testing__C188132__LVMC-11-30-060-B__pedestrian/runner.py --check --scene work/testing__C188132__LVMC-11-30-060-B__pedestrian/scene-yield_before_vehicle.json --map work/testing__C188132__LVMC-11-30-060-B__pedestrian/candidate-overpass.xodr` and the analogous commands for the other two cases; retained check logs and hashes are in `result.json`.

Next CPU work: package exact inline constructions and canonical stage proposals; author case-specific finalizer and diagnostic recipes, positive/negative compatibility proofs, process-saved tests, and independent sealed delivery audit with four-video full decode. Add all-participant Native inventory and original deck access/readback checks to the capture and audit before claiming readiness. Physically verify the overpass structure and usable access during later authorized CARLA execution. Do not promote this partial package.

### Exact offline materialization

`build_offline.py` generated `draft-offline-manifest.json` and three source-hashed inline constructions under `cases/`. `runtime.py offline` materialized each exact case in `.runtime-work/`, ran `runner.py --check` and its bundled exact-scene test, and passed. Retained outer and inner logs and SHA-256 values are in `result.json`. The first attempt used a relative `--python` path and failed because the runtime changes cwd to the materialized bundle; rerunning with the absolute pinned interpreter passed. No Native simulation started. These drafts lack finalizers/compatibility and are not the strict `execution-manifest.json`.

### Exact gate and artifact integrity

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C188132__LVMC-11-30-060-B__pedestrian --complete` exited 0 (`exact-static.log`). Adding `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain` (`exact-strict.log`), consistent with the truthful partial status. All ten declared test log hashes were independently rechecked; the focused nine-test log SHA-256 is `b64a009a9f868036cc97a0e428bd1ec2a628e1db7943ef1421da7a2911951856`. Assignment files are UTF-8 text, under 2 MiB each, with no trailing whitespace or conflict markers.

## 2026-11-23 all-vehicle and four-camera source checkpoint

`native_sample` now inventories every original Native vehicle actor on each tick and checks that the selected vehicle's position and velocity match its inventory entry. `measure_original` rejects missing, duplicated, nonfinite or disagreeing inventory rows and reports the full observed actor-ID set. `audit_pair` rejects a changed all-vehicle source even when the selected vehicle trajectory stays fixed. Roadway classification remains unresolved pending original map review; merely listing Native actors does not establish that all were upon the roadway.

`media_audit.py` independently verifies the source-manifest hashes for four named original MKV streams and camera-frame joins, the 20 Hz 900-frame frame map, camera resolution/format joins, ffprobe stream counts and complete ffmpeg decode. `runner.py` writes the media audit before sealing a Native capture. The two-frame, small-resolution unit fixture exercises all four decodes and rejects a stale stream, missing camera join and incorrect frame count; it does not establish actual overpass visibility. `build_offline.py` includes the auditor and rebuilt all three inline constructions. All three exact `runtime.py offline` checks pass from these updated constructions in `.runtime-work/c188132-*-media-final-nov23`; logs and current hashes are listed in `result.json`.

The focused suite now passes 13 tests (`cpu-tests.log`). Current CPU work still required for readiness: canonical semantic proposals, case-specific finalizer and diagnostic recipe, positive/negative compatibility, process-saved and sealed delivery acceptance, plus review of the tunnel branch and an actual source-backed designation for the exception. Physical Native bridge access, pixels and motion remain later checks. Status remains partial.

Final scoped checks for this checkpoint: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C188132__LVMC-11-30-060-B__pedestrian --complete` passed (`exact-static.log`). The exact command with `--require-delivery-ready` failed only on `Preparation acceptance failed: partial/missing packages remain` (`exact-strict.log`), matching `result.json` status `partial`. The first static retry exposed a generated-log name beginning `offline-`; those three returned logs were renamed to `construction-*-media-final.log` before the passing static recheck.
