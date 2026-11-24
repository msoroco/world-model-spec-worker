# testing__C214977__NRS-484B-450-1e__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(e) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: On a crosswalk.
Assigned branch(es): Parking on a crosswalk in a residence district.
Cell: C214977 (residence_district, park, crosswalk); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C214977__NRS-484B-450-1e__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The frozen evidence inventory contains zero accepted recordings. The exact NRS 484B.450(1)(e) branch has no numeric threshold or judgment-range entry for this law/actor. `case-plan.json` now defines eight planned cases for parking on/off a mapped crosswalk, separate stopping and standing acts, traffic-conflict necessity, and law, police, and official-device direction exceptions. Seven controlled comparisons join these cases. Each case has a physical-risk assessment; the source must establish an actual residence-district highway crosswalk, marking status, and applicable signal governance. These are planned recordings, not executed or accepted recordings.

`crosswalk.py` implements source-hashed site and driver inputs, Native crosswalk and ego readback, route/exception adapter calls, vehicle-footprint polygon overlap, actual halt activity and exception sources on contiguous original 20 Hz rows, a sealed 900-frame four-camera source audit, and comparison-fixed-condition checks. `tests/test_crosswalk.py` uses fake adapter calls and source-shaped rows, including negative tests for missing frontage source, corrupt hash, timing gap, and missing camera. The saved-source checker does not replace the pinned media decoder or physical review.

Checks: focused 10-test suite passed (`cpu-tests.log`); exact `worker_check.py --assignment ... --complete` passed (`cpu-static-check.log`); exact strict check failed with `Preparation acceptance failed: partial/missing packages remain` (`cpu-strict-check.log`). SHA256 values are in `result.json`. CPU preflight passed with pinned Lean 4.28.0 and the current Python environment.

Next CPU work: bundle every exact case with config/construction/runner and per-case measurement contracts; add canonical semantic stage proposals; run pinned `runtime.py offline` and positive/negative `runtime.py compatibility` for each case and any justified fallback; bind case-specific saved-only processing and independent delivery/comparison audit receipts to the execution manifest; rerun exact strict gate. After CPU readiness, local CARLA must verify driven parking, realized body/crosswalk geometry, four-camera visibility, and physical completion. No legal verdict follows from the fixture checks.

## Exact offline expansion

All eight selected case bundles in `cases/*/construction.json` passed pinned `.venv-cpu/bin/python runtime.py offline` (one `proof-offline-*.log` per case, commands/hashes in `result.json` and `execution-manifest.json`). The bundles retain the same four-view 20 Hz/45 s profile and exact case identity. `proposals/cases.json` maps all eight to a draft canonical case stage. The offline entrypoint runs identity and bundled CPU checks. The Native path intentionally raises until a real CARLA adapter, source capture, and recording handoff exist; offline success is not Native or delivery readiness.

The exact static gate passed after these additions. The exact strict gate still fails at truthful partial status. Next CPU tasks are to build the Native adapter/recorder, positive and negative pinned compatibility recipes and per-case finalizer bindings, risk-based fallback construction/proofs, complete semantic proposals, and saved-only delivery acceptance audits.

## 2026-11-24 source-bound Native and saved checkpoint

`native_capture.py` now collects one original 20 Hz, 900-frame Native row and four camera readbacks per tick through an injected adapter. It binds sealed site and vehicle inputs, checks frame/time/case/actor identities, recomputes crosswalk footprint and halt measurements, seals original actor/frame/camera rows, and invokes brake and cleanup even on a mid-run failure. `saved_crosswalk.py` independently reopens the sealed receipt and source inputs, joins all 900 original frame and camera identities, and rejects tampered rows or measurement drift. Its CLI takes source and attempt roots, a receipt and exact case JSON; it does not claim media decode, physical completion, pixel coverage or a legal verdict. The fixture adapter in `tests/test_native_capture.py` is CPU-only.

`crosswalk.py` now rejects disjoint collinear polygon edges as overlap and counts only the exception source named by the exact case. The tests exercise both corrections. All eight inline construction bundles were rebound to the changed source and passed pinned `runtime.py offline` into new ignored `.runtime-work/*-v4` attempts. Focused suite: 15 tests passed in `cpu-tests.log`. The exact assignment static check passed in `cpu-static-check.log`; the strict check in `cpu-strict-check.log` exits 1 on truthful partial status. `result.json` carries current hashes.

Remaining CPU work: bind the Native collector to a concrete CARLA adapter and four media recorders; implement actual control policy and source-proven law/police/device/traffic-conflict packets; author exact diagnostic positive and missing-source negative compatibility for each of eight cases; add canonical semantic stage proposals and per-case measurement contracts; bind pinned `process-saved`, full media decode, independent delivery and comparison audits to each manifest case; assess and prove risk-justified fallbacks. The source collector and fixture do not establish those delivery proofs. The local capture must later verify crosswalk, residence-district highway context, activity, visibility, and physical outcome from original evidence.

Draft semantic proposals now include `proposals/relevance_batch.json`, `relevance.json`, `template.json`, `bindings.json`, all eight selected cases in `cases.json`, three value-free exception observation files, and a SHA-indexed `semantic-index.json`. These preserve the verbatim law and keep exception authority, necessity, district context and legal judgment unresolved. They require local review and are not canonical adoption.
