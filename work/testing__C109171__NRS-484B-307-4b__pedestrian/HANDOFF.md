# testing__C109171__NRS-484B-307-4b__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(4)(b) — Where the signal is a green turn arrow alone: Pedestrians facing such a signal shall not enter the highway until permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): Facing arrow before highway entry.
Cell: C109171 (intersection, enter_road, turn_arrow); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109171__NRS-484B-307-4b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 source-gated construction checkpoint

No accepted recordings are listed in the frozen evidence inventory. The exact law restricts pedestrian highway entry while facing a sole green turn arrow until a different device permits proceeding. The reference to NRS 484B.283(1)(d)(1)-(4) remains an unresolved permission source, not a permission inferred from the arrow.

`case-plan.json` now has four exact cases: `arrow_wait`, `arrow_early_entry`, `arrow_walk_entry`, `arrow_walk_wait`. It isolates measured entry without other permission, separate-device permission, and the optional choice to wait after permission in three controlled comparisons. The comparison suffixes are under the assignment prefix in the plan. Every case carries the Native site/signal/visibility risk. The case plan has selected requirement dispositions and a source-cited gap because the frozen evidence list is empty.

`native_scene.py` checks SHA-256 of original map, vehicle-head and separate pedestrian-device sources; rejects conflated heads, ungoverned pedestrian devices, routes that start inside or never enter the surveyed highway polygon, non-sole-arrow frames and altered/missing source packets. It measures the first boundary entry and the separate device indication without a legal verdict. `pedestrian_control.py` issues injected CARLA-shaped walker controls for the exact wait and entry cases; it does not treat the arrow as permission. `comparison_audit.py` checks six fixed source/camera/duration conditions, sole-arrow frames and each measured deliberate difference; it returns no physical acceptance or legal verdict. These modules are portable construction drafts, not a pinned Native manifest.

Proofs: CPU preflight passed in `cpu-preflight.log`; 17 tests passed in `cpu-native-tests.log`; assignment `--complete` passed in `cpu-static-check.log`; exact assignment `--complete --require-delivery-ready` failed at the expected `Preparation acceptance failed: partial/missing packages remain` in `cpu-strict-check.log`. `result.json` binds SHA-256 of each log.

Next CPU work: bind a reviewed Native intersection/site/signal packet to all four exact bundles; create semantic stage proposals, executable CARLA capture and frame-map code, source-bound finalizer and diagnostic recipes; run offline and positive/negative compatibility for each case; implement saved-only processing and independent media/delivery audits with rejection tests; bind the canonical manifest and rerun the exact strict gate. Original site, arrow and pedestrian-device existence remain unverified; no available recording or CPU fixture establishes physical visibility.
