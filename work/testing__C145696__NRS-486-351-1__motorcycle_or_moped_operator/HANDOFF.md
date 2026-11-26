# testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator

Status: partial CPU delivery preparation. Eight exact cases and six comparisons are authored; original recording remains source gated.

Exact law: NRS 486.351(1) — A person, except a police officer in the performance of his or her duty, shall not drive a motorcycle or moped between moving or stationary vehicles occupying adjacent traffic lanes.
Assigned branch(es): One-way multilane between-vehicle driving.
Cell: C145696 (one_way_multilane, lane_split, other_vehicle); actor: motorcycle_or_moped_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable branch checkpoint

Original law and scope reread: NRS 486.351(1) includes moving or stationary vehicles in adjacent lanes, motorcycle or moped, and the police officer performing duty exception. The eight exact planned variants in `case-plan.json` span both occupants stationary, each independently moving, both moving, a within-lane path control, police on/off duty, and moped class. Six comparisons name fixed conditions and differences. These are planned observations, not verdicts. No accepted recording exists in the frozen evidence inventory; no exact-law judgment range is supplied.

`lane_split.py` constructs a lazy Native request only after source-surveyed one-way adjacent lane identity, drivable route and measured body clearance pass. `execute_native` calls backend spawn, actor readback and route controller and destroys owned actors in reverse order. `measure_original` requires contiguous original frame IDs and exact participant IDs, retains all body geometry and observed speeds, and exposes candidate between-vehicle frames without an invented statutory distance or duration cutoff. `audit_saved` checks source hashes, all three participant IDs, original frame map, four complete decoded cameras and independent pixel/physical reviews. `audit_comparison` rejects fixed-condition drift and missing source decode proof.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator/tests -v` passed 7 tests; `cpu-tests.log` and `result.json` bind its SHA-256. `.venv-cpu/bin/python worker_check.py --assignment testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator --complete` passed static checks. The exact strict command with `--require-delivery-ready` failed at partial/missing packages, as recorded in `cpu-strict-check.log`.

Remaining CPU work: select/source a Native map and supported motorcycle/moped blueprint for each exact case; author full delivery manifest, config, runner, source-hashed case diagnostics, semantic stage proposals, and saved-only process bindings. Run each case and justified fallback through exact offline and positive/negative compatibility, then source-bound delivery and comparison proof commands. Recheck physical-risk fallback need using actual source readback. Retain status partial until the exact strict gate exits 0. Later local Native motion, four camera pixels, and physical completion remain unverified.

## 2026-11-26 CPU delivery construction in progress

The current bundle has eight exact primary constructions and eight source-hashed fallback constructions. A reviewed original scene packet gates map and OpenDRIVE identity, one-way adjacent lane survey, body clearance, participant blueprints, chapter vehicle classification, operator identity, police status, and performance of duty. The original runner creates three physical Native actors, records actual actor and lane readbacks for 900 consecutive 20 Hz frames, captures four synchronized FFV1 cameras, seals source hashes, restores world settings, and defers legal and physical interpretation to saved review. The fallback shifts the ego spawn three metres upstream only after an original spawn or incomplete-passage trigger; exact case variables and capture contract stay fixed.

Canonical relevance, template, binding and case proposals passed the pinned semantic stage validator. The source-shaped diagnostic specifications are synthetic, explicitly marked diagnostic, and each generates 900 participant/trace/frame rows, four 900-frame videos and a Native adapter graph per frame. All 16 exact primary/fallback offline checks passed. Eight three-outcome physical probes and ordered capture/owner/saved lifecycle probes passed, and their formal receipts passed the pinned physical-preparation validator. The first primary and fallback case passed full positive/negative package compatibility through saved analysis, Native validation, Core conversion, Lean decoder, render and video decode. Other exact cases remain in progress; status is partial until each receipt and the strict scoped gate pass.

The independent `delivery_audit.py` accepts only case-bound, source-hashed 900-frame/four-camera diagnostic integrity as a CPU positive; its original-only mode rejects diagnostics. Original delivery additionally requires original acquisition seals, an independent pixel review packet, and physical completion. `comparison_audit.py` checks the six fixed-condition contrasts against the saved source streams, with independent original duty/classification hashes required when those recordings exist. The CPU proof driver will bind positive and negative case and comparison logs after the remaining compatibility runs complete.
