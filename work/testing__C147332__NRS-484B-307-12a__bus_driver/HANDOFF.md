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

`scene_construction.py` authored four exact engineering scene drafts under `cases/`, with a 90 m two-lane one-way OpenDRIVE candidate reused as local bytes from same-cell C147332 12b engineering work. Its checks bind exact lane IDs, 3.6 m widths, bus route, full-width clearance, signal placement above each lane, four cameras at 20 Hz, and one map SHA. This map and the signal art are engineering candidates; highway status, official-device provenance and Native import are unverified. All `official_device_source` fields remain null rather than implying a reviewed source.

`green_lane_measurement.py` joins original bus, per-lane signal and camera references by contiguous frame and time with source SHA-256 fields. It requires an original full bus footprint fully within an indicated lane for its conservative `permission_observed` physical observation; records movement separately and leaves legal judgment unresolved. It rejects missing hashes, broken joins, changed lane geometry/device source, wrong-way lane mapping and polygon spill. Its two comparison functions reject an unselected signal change, altered bus motion in the indication pair, changed green indication in the motion pair and missing measured differences. `cpu-green-tests.log` passes 8 tests; `cpu-green-scene-build.log` records all four authored drafts. Their hashes are in `result.json`.

Pinned CPU preflight and update check pass with Lean 4.28.0 and no pauses. The repository three-test suite and exact C147332 12a partial static gate pass. The result stays partial: reviewed source binding, executable Native bundles/controllers and finalizer integration, canonical semantic proposals, exact offline and positive/negative compatibility, three physical CPU outcomes, independent delivery/comparison audits, and local integration remain CPU construction. Actual motion and pixels remain later Native verification. No frozen input, runtime, or batch file was edited; no Git command was run.
