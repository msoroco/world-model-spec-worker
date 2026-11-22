# testing__C147332__NRS-484B-307-12b__bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(12)(b) — Whenever signals are placed over the individual lanes of a highway, the signals indicate, and apply to drivers of vehicles, as follows: A red “X” symbol means a driver facing the signal must not enter or drive in any lane over which the red signal is shown.
Assigned branch(es): Bus approach or lateral entry into a red-X lane..
Cell: C147332 (one_way_multilane, travel, lane_signal); actor: bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147332__NRS-484B-307-12b__bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-22 exact red-X case construction start

Status remains **partial**. Four exact case IDs are now planned: `__adjacent_travel`, `__lateral_entry`, `__red_lane_stand`, and `__red_lane_drive`; two comparisons isolate lateral entry and in-lane longitudinal driving under a red X. `bus_route.py` builds distinct center waypoint targets, and `build_scene_drafts.py` emitted all four source-explicit `cases/<suffix>/scene.json` drafts. `lane_signal_measurement.py` measures full bus-footprint overlap and red-X entry/driving on synchronized original body, signal and camera frames, requiring a facing official-device packet hash. Six tests pass in `cpu-tests.log`; exact static `worker_check.py --assignment testing__C147332__NRS-484B-307-12b__bus_driver --complete` exits 0 (`.runtime-work/c147332-static-next.log`). No legal verdict or realized motion is claimed.

Next CPU actions: establish the original highway and official-device source packet with overhead signal-to-lane and bus-facing association; turn the drafts into CARLA-lazy Native map/prop/bus controller bundles; emit original source histories and four camera streams; author canonical semantic stages and finalizers; run pinned offline, positive/negative compatibility, saved-only and independent delivery/comparison audits with source tamper negatives. Keep partial until the exact strict gate passes. Actual CARLA motion/pixels and legal sufficiency remain later local review. Frozen inputs, runtime and batch were preserved; no Git command was run.

Source-review guard follow-up: `source_review.py` requires retained original highway and official-device bytes, SHA matches, reviewer/citation, bus-facing overhead red X and its governed lane before a Native attempt; the current assignment has no such reviewed packet. The measurement also rejects changed lane bounds or official packet within a comparison. Eight CPU tests pass in `cpu-tests.log`. Resume by collecting and independently reviewing genuine source bytes and binding this validator into the Native pre-spawn path, then complete the delivery package. The test packet is temporary fixture data only. No Git command was run.

Saved finalizer follow-up: `analysis.py` now hashes acquisition and reviewed site packet, each original body/signal/camera channel and every referenced original source file before joining frame/time into `lane_signal_measurement.py`. A changed signal stream fails before measurement. Ten CPU tests pass in `cpu-tests.log`; exact static acceptance remains the next check. The temporary positive fixture tests software only, with no claimed official-device or physical evidence. Resume source review and Native bundle construction, then pinned saved-only and independent delivery proofs. No Git command was run.
