# testing__C125745__NRS-484B-250-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.250(2); with 484B.250(5) — When two vehicles enter an intersection from different highways at approximately the same time, the driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.
Assigned branch(es): Measured crossing-entry timing at a median-opening intersection..
Cell: C125745 (median_opening, travel, stop_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 1. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 1 exact law/actor ranges. These are unmeasured construction targets. 0 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 exact entry timing construction checkpoint

`case-plan.json` now has three exact physical timing targets `__entry_below`, `__entry_inside`, and `__entry_above` from the source-hashed `judgment-probe-plan.json` and two controlled comparisons sharing the inside case. Their ego-minus-other target values are -2.860000042617321, -0.02500000037252903, and 2.810000041872263 seconds. These are unmeasured training-range coverage targets, not legal cutoffs. The existing `__precedence` and `__advance` accepted metadata remain in the evidence review and are not treated as measured witnesses. `case-plan.json` SHA256 `f28b11cd7847852d279984d30924f327571d6a1931f745e19e07b4bfc374032b`.

`entry_timing.py` SHA256 `cc3f3dde73d0d249f201176c25793d90385f6eb838a06254dd7d3350d779f334` hash-checks a saved exact-case original trace, source IDs for map/intersection/highways/devices, different roadway identities, 20 Hz frame/time continuity, actor identities and complete footprint polygons. It finds each actor's first footprint intersection transition, retains consecutive sample brackets and reports the ego-minus-other upper timestamp without interpolation. It explicitly leaves approximate timing, right-of-way and exceptions undetermined. `test_entry_timing.py` SHA256 `5cad67bcb2c0b626d366a991b178f1d6a6abcd96f154f73ef57233196b3c5650` exercises one measured fixture and missing/source-drift, wrong-case, frame-gap, same-highway and unbracketed-entry rejection paths.

Pinned proofs: four focused tests exit 0, `cpu-tests.log` SHA256 `e001fb9af705cdcb3c6a865c6ded66cfb5eaad273677503e6d42bc02d7f2f1a7`; preflight exits 0, `cpu-preflight.log` SHA256 `520ab9faa07b3c4125d167d7c2eb7d6853e36781f119e9c80508d38924468236`; scoped static exits 0, `assignment-check.log` SHA256 `8493df8194df8549b72fe19248c427f32779152be93b417fcf660fb3eb318a24`. Exact scoped strict exits 1 on truthful partial, `assignment-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Next CPU work: source-review the actual fixed-cell median-opening geometry, intersection boundary, both distinct highways and stop-sign placement/authority/operation; author three executable timing controls and original capture paths, exact bundles/manifest, semantic proposals, positive and negative compatibility recipes, saved-only processing and independent delivery/comparison audits. Independently decide whether official-control and other statutory exceptions make this cell inapplicable before any legal conclusion. Physical motion and camera visibility remain later checks.
