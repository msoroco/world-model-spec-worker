# testing__C147332__NRS-484B-307-12a__bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(12)(a) — Whenever signals are placed over the individual lanes of a highway, the signals indicate, and apply to drivers of vehicles, as follows: A downward-pointing green arrow means that a driver facing the signal may drive in any lane over which the green signal is shown.
Assigned branch(es): Green permission across one or more same-direction lanes..
Cell: C147332 (one_way_multilane, travel, lane_signal); actor: bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147332__NRS-484B-307-12a__bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 green-arrow construction and measurement continuation

The exact law grants permission to drive in a lane with a bus-facing downward green arrow over it; it does not require bus movement. `case-plan.json` now names four exact probes: `green_selected_drive`, `adjacent_dark_drive`, `second_green_drive`, and `green_selected_stand`. The two comparisons hold the adjacent bus route fixed while adding a green arrow over its lane, and hold green-arrow coverage fixed while changing bus motion. The adjacent dark case only tests absence of this subsection's permission, not a violation conclusion.

`scene_construction.py` authored four exact engineering scene drafts under `cases/`, with a 90 m two-lane one-way OpenDRIVE candidate derived from same-cell C147332 12b engineering geometry and renamed for the green-arrow case. Its checks bind exact lane IDs, 3.6 m widths, bus route, full-width clearance, signal placement above each lane, four cameras at 20 Hz, and one map SHA. This map and the signal art are engineering candidates; highway status, official-device provenance and Native import are unverified. All `official_device_source` fields remain null rather than implying a reviewed source.

`green_lane_measurement.py` joins original bus, per-lane signal and camera references by contiguous frame and time with source SHA-256 fields. It requires an original full bus footprint fully within an indicated lane for its conservative `permission_observed` physical observation; records movement separately and leaves legal judgment unresolved. It rejects missing hashes, broken joins, changed lane geometry/device source, wrong-way lane mapping and polygon spill. Its two comparison functions reject an unselected signal change, altered bus motion in the indication pair, changed green indication in the motion pair and missing measured differences. `cpu-green-tests.log` passes 8 tests; `cpu-green-scene-build.log` records all four authored drafts. Their hashes are in `result.json`.

Pinned CPU preflight and update check pass with Lean 4.28.0 and no pauses. The repository three-test suite and exact C147332 12a partial static gate pass. The result stays partial: reviewed source binding, executable Native bundles/controllers and finalizer integration, canonical semantic proposals, exact offline and positive/negative compatibility, three physical CPU outcomes, independent delivery/comparison audits, and local integration remain CPU construction. Actual motion and pixels remain later Native verification. No frozen input, runtime, or batch file was edited; no Git command was run.

Final strict batch gate after scene-map edit exits 1 at `Preparation acceptance failed: partial/missing packages remain`; log `.runtime-work/full-strict-c147332-12a-green-final.log`. The exact static assignment check still passes. Non-Git return scan found 9,906 UTF-8 files, largest 1,846,854 bytes, no size or whitespace/marker issues.

## 2026-11-23 saved source and comparison continuation

`source_review.py` now requires retained, SHA-bound original highway and official-device source files, reviewer/citation fields, bus-facing overhead downward green arrow, explicit governed lane IDs, and a Native asset identifier. This is a precondition checker, not a legal determination; no real reviewed source packet is present in this assignment. `analysis.py` binds the reviewed packet and all three original channel files to `acquisition.json`, checks every row's retained source file and hash, joins contiguous frame/time observations, and invokes `green_lane_measurement.measure`. Its report keeps legal and physical acceptance false. It does not yet emit the pinned Native `result.json` or converter channels.

`comparison_audit.py` independently binds two preserved attempts, verifies exact ordered case IDs and fixed scene/map/bus/device identities, then uses original frame observations to check the second-lane dark-to-green contrast or the green-permission drive-versus-stand contrast. It rejects changed originals and wrong case ordering. `tests/test_saved_analysis.py` uses temporary **synthetic unit-test sources** solely to prove positive/negative custody and comparison branches; those sources are not returned as official highway/device evidence. The assignment test command `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c147332-12a-runtime PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C147332__NRS-484B-307-12a__bus_driver/tests -v` passes 13 tests; `cpu-green-tests.log` SHA is recorded in `result.json`.

Next CPU work: build the four inline Native bundles and controller/capture sources from the exact scene drafts, add per-case physical-risk/fallback decisions, emit pinned saved `result.json` and converter channels, author canonical semantic proposals, run exact offline and source-bound positive/negative compatibility proofs, and implement the independent delivery audit. Then rerun exact strict readiness. Keep the assignment partial until those proofs pass. No GPU prerequisite prevents this CPU construction.

Current validation: `.venv-cpu/bin/python runtime.py preflight` passed with Lean 4.28.0; `worker_check.py --updates` found version 0 and no pauses; three repository tests passed. `.venv-cpu/bin/python worker_check.py --assignment testing__C147332__NRS-484B-307-12a__bus_driver --complete` passed in `.runtime-work/c147332-12a-static-current.log`. The complete strict gate exited 1 with `Preparation acceptance failed: partial/missing packages remain` in `.runtime-work/full-strict-c147332-12a-current.log`. A non-Git scan checked 9,910 returned UTF-8 files: largest 1,846,854 bytes, no oversize, trailing whitespace or conflict markers. No Git command was run.

## 2026-11-23 four inline Native bundle continuation

`native_construction.py` binds one 90 m, two-lane OpenDRIVE source, both 3.6 m same-direction lanes, exact bus route and two individually aligned heads for each of four exact cases. `native_driver.py` implements a measured-state closed-loop bus request or hold brake and calls CARLA actor creation for both heads and the full-size bus. `runner.py` has a CARLA-free `--check` and requires a retained reviewed source packet with exact green-lane association before Native dispatch. `native_capture.py` now records the original bus footprint, two-head transforms, lane signal states, controller requests and four camera frame identities at 20 Hz for 18 s, with acquisition hashes and restoration checks. These are authored code paths; no Native run or genuine source review occurred here.

`build_constructions.py` produced four primary inline bundles and four `fallback1` bundles with both heads raised from 6 to 7 m for the specific bus/head co-visibility risk. The exact case IDs, route, cameras, duration, required observations and comparison variables stay fixed. `execution-manifest.json` records each construction hash, risk, trigger and pinned offline receipt; it remains partial. The four primary and four fallback `runtime.py offline` checks all exited 0. `tests/test_native_driver.py` exercises fake-world creation calls for both head positions and the bus in all four cases; the full assignment suite passes 14 tests. Log paths and SHA-256 values are in `result.json` and the manifest.

Next CPU work: complete `analysis.py` with pinned Native `result.json` and converter channels, implement independent delivery audit and canonical semantic proposals, add source-hashed case-specific diagnostic recipes and measurement contracts, run positive/negative compatibility for every primary/fallback, and complete the physical CPU preparation receipts. Review the genuine highway/official-device source packet before any Native dispatch. The assignment remains partial; eight offline checks do not establish physical acceptance or delivery readiness.
