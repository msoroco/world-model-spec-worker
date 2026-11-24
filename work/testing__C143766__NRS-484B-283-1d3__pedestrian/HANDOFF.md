# testing__C143766__NRS-484B-283-1d3__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(d)(3) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: Whenever signals exhibiting the words “Walk,” “Don’t Walk,” “Wait” or similar symbols are in place, such signals indicate as follows: While the “Don’t Walk” or “Wait” indication or an upraised hand symbol is illuminated and flashing but is not accompanied by a countdown timer, a pedestrian may not proceed to cross the highway, but a pedestrian who entered the highway lawfully pursuant to subparagraph (1) [NRS-484B-283-1d1] may continue to cross the highway but must proceed to a curb, sidewalk, safety zone if one is provided or other place of safety before the “Don’t Walk” or “Wait” indication or an upraised hand symbol is illuminated and steady.
Assigned branch(es): Continuation toward sidewalk conditional on lawful prior entry.
Cell: C143766 (nonmotorized_trail, travel, sidewalk); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C143766__NRS-484B-283-1d3__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
## 2026-11-23 exact crossing construction and original signal checkpoint

Frozen accepted evidence contains zero recordings. `case-plan.json` now identifies seven exact cases: prior-Walk entry with sidewalk arrival before or after steady, new entry during flashing, prior-Walk arrival at a curb, provided safety zone or reviewed other place of safety, and a countdown-present activation probe. Six controlled comparisons isolate entry phase, arrival timing, destination, and countdown. A Walk-phase entry is an observed signal condition; whether it was lawful under NRS 484B.283(1)(d)(1) and whether any cited exception applies remain unresolved.

`pedestrian_crossing.py` requires distinct sourced trail, actual highway crossing, accessible sidewalk, facing pedestrian signal and connected routes to four candidate safety destinations. Its CARLA-lazy constructor requests an exact signal schedule, pedestrian spawn and route. `measure_original` checks 900 original 20 Hz frames, stable signal/pose/site sources, Walk-to-flashing-to-steady transition, first highway entry, countdown state, and arrival at the selected destination. It keeps prior lawful entry, exception applicability, and legal judgment unresolved. Engineering route proximity is not a legal safety definition.

`tests/test_pedestrian_crossing.py` exercises construction and original measurement for all seven exact cases; negative fixtures reject disconnected routes, missing destination sources, wrong signal facing, countdown drift, frame/time drift, source drift, invalid signal transition, and spawn failure. Four focused tests pass. Pinned runtime preflight and scoped static pass; exact strict exits 1 because the package remains partial. There is no `runtime.py offline` receipt yet because exact runner/config/manifest bundles remain CPU work.

Proof hashes: `cpu-tests.log` `cb7876f643ecead92d3a197e3d51355b0f00c1db1d132e6b637c64548b4c3305`; `cpu-preflight.log` `00aa8e0824b42ef2c7ac14d7384dc7f8cab2647f45afc0a984c1adc8e7efaba3`; `cpu-static-check.log` `14631691632d685db7c94f17173f87fb0c1c029ec3a9a24bd05ac5741e0c20a5`; `cpu-strict-check.log` `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1).

Next CPU work: bind actual original site and display source bytes, implement a Native pedestrian/signal adapter and exact seven-case delivery bundles, prove each with offline and positive/negative compatibility, author semantic proposals and selected-requirement finalizer, and test independent saved delivery/comparison audits. Physical pedestrian route and display visibility await original Native review.
