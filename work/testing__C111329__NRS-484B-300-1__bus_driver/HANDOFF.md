# testing__C111329__NRS-484B-300-1__bus_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.300(1) — Except as otherwise provided in NRS 484B.307 [NRS-484B-307-2a, NRS-484B-307-2b, NRS-484B-307-3a, NRS-484B-307-4a, NRS-484B-307-4b, NRS-484B-307-5a, NRS-484B-307-6a, NRS-484B-307-7a, NRS-484B-307-8a, NRS-484B-307-8b, NRS-484B-307-8c, NRS-484B-307-8d, NRS-484B-307-8e, NRS-484B-307-9a, NRS-484B-307-9b, NRS-484B-307-9c, NRS-484B-307-11, NRS-484B-307-12a, NRS-484B-307-12b], it is unlawful for any driver to disobey the instructions of any official traffic-control device placed in accordance with the provisions of chapters 484A to 484E, inclusive, of NRS, unless at the time otherwise directed by a police officer.
Assigned branch(es): Intersection travel under an applicable official device instruction..
Cell: C111329 (intersection, travel, traffic_control_device); actor: bus_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-300-1__bus_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

Exact cases: `__red_hold`, `__red_enter`, `__red_police_proceed`, `__green_proceed` (prefix `testing__C111329__NRS-484B-300-1__bus_driver`). Comparisons: `red_instruction_conduct`, `contemporaneous_police_direction`, `device_instruction`. The baseline red-entry case is reused across contrasts; no accepted recording or legal result is claimed. Each case has a concrete physical bus-clearance, phase and four-camera visibility risk assessment in `case-plan.json`; no untested fallback is claimed.

`device_scene.py` validates SHA-sealed original map/device/route/authority packets, governing approach, connected bus route and bus clearances; creates the Native bus with map, signal head and blueprint readback; measures original-frame signal aspect and bus-front stop-line crossing. `device_control.py` exercises red hold, red entry, green proceed and source-gated officer-directed proceed. `comparison_audit.py` independently rejects changed fixed conditions, absent original trace/exception sources and missing observed differences; `audit_delivery` rejects missing original frames, video, phase and line-entry evidence. These engineering checks do not decide official placement, police authority, NRS 484B.307 applicability or legal compliance.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-300-1__bus_driver/tests -v` exited 0 with seven tests; `cpu-tests.log` SHA256 `cb6bec262e4681bfa43d971a263ce7c503f7cf0634bf06a6708006aa448f7a44`. Exact strict gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-300-1__bus_driver --complete --require-delivery-ready` reaches `Preparation acceptance failed: partial/missing packages remain`; retained `cpu-strict-check.log`. Status remains partial.

Next CPU work: author canonical semantic proposals, full per-case runner/config/construction/measurement bundles and execution manifest; provide source-hashed case-specific diagnostics, offline and positive/negative compatibility receipts, saved-only post-capture path and complete delivery audit integration; rerun focused tests and strict gate. Physical Native replay later verifies motion, actual bus clearance and camera coverage.
