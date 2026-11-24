# testing__C229925__NRS-484B-450-1j__vehicle_stopping_person

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(j) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within 20 feet of a driveway entrance to any fire station and, on the side of a highway opposite the entrance to any fire station, within 75 feet of that entrance.
Assigned branch(es): Opposite-side destination stopping under the 75-foot clause..
Cell: C229925 (road, stop_stand, fire_station_entrance); actor: vehicle_stopping_person.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229925__NRS-484B-450-1j__vehicle_stopping_person --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 fire-station entrance geometry checkpoint

`case-plan.json` now holds fifteen exact unexecuted cases and thirteen controlled comparisons. The opposite-highway-side branch has nominal 74/75/76-foot stop probes, stand/park contrasts and traffic-conflict, law, police and official-device circumstances. The entrance-side branch has nominal 19/20/21-foot probes. Fire-station identity, highway public use and side are separate controls. Nominal positions are construction targets, not measured or legal conclusions.

`fire_entrance_measurements.py` accepts only a hash-sealed original Native context and 20 Hz trace. It requires source references for fire-station identity, entrance and highway boundaries, public dedication/use, entrance side, stopping person/purpose and each exception circumstance. It retains both raw entrance endpoints and vehicle eight-vertex positions through sampled vertex-to-entrance distances and signed lateral coordinates. The 20- and 75-foot metric conversions are references. The legal distance convention, actual opposite side of the highway, necessity and direction exceptions stay unresolved. Diagnostic fixtures are rejected as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Seven focused tests passed (`cpu-fire-tests.log`, SHA256 `b949af91c081e856fe63034b9d4b26c8d90e74b3a387b9c2e0c7263fa574f047`). Scoped static check passed (`assignment-check.log`, SHA256 `da746edc9c73349956601647ba7b99fac52fb13ee2be4e3a152116b6fbb97d74`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `b9657969434c3fcda77eb7c5ef8e498bc2eb3a3c47e9f9146f666814e4d406d1`, measurement `c67d65e45e1b193560eff490418f41d861d4612aada7d87ac36d55755e56c271`, focused tests `fdc5fbdeaaa07150eb5d7b9ff42b0731094661577910e28a2375fd4f98c6e039`.

Remaining CPU work: bind a reviewed Native fire-station entrance and public-highway map, independent person and exception facts, construct fifteen physical scenes/controllers and synchronized four-camera original capture, validate full vehicle-footprint/highway-side geometry, then implement finalizers/proposals, exact offline and positive/negative compatibility, saved-only delivery and thirteen comparison audits. Physical and legal acceptance remain unverified.
