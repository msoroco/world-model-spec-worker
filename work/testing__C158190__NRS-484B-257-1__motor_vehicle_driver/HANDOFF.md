# testing__C158190__NRS-484B-257-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(1) — Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Yield sign; neither stop line nor crosswalk; nearest-view location..
Cell: C158190 (one_way_to_two_way_intersection, travel, stop_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 2. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 4. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 4 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 CPU checkpoint

The branch requires a proper yield sign, no stop line, no near crosswalk, nearest point with a view of approaching through traffic, slowdown or stop, and yielding to through vehicles already in the intersection or posing an immediate hazard during the crossing. Police and traffic-signal control are statutory exclusions. The source cell is annotated `stop_sign`, so construction must actually provide a yield sign and read it back; annotation alone is insufficient. `case-plan.json` now has two frozen accepted-source review candidates and three unselected controlled yield cases, with two isolated comparisons.

`yield_view_measurement.py` binds original source SHA256, requires site readback, rejects a present line/crosswalk or active control exclusion, chooses the nearest sampled station with through-traffic view, and reports pre-entry speed reduction and through-vehicle IDs at entry. It does not invent a legal immediate-hazard cutoff. Five synthetic CPU tests pass. The frozen speed range starts at zero, so its below-zero planning target is physically impossible; no cutoff is claimed.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `d084ff7ffcfc347f6cff5fc6b9d645fa7c466bcbf744b5d46184b24572195227` |
| `yield_view_measurement.py` | `e477dc13f95802d12cbe77fdd0fab11047ac999d6715dab343f7b30491bb770f` |
| `tests/test_yield_view_measurement.py` | `8fd15d82de3b93cc3de68feb74b03df3155da14c0bc8e646388734c905f77841` |
| `preflight.log` | `2f34644ce84bfcd860e001ee488461f6e0672be17b3c0465047933b0d06f3501` |
| `unittest.log` | `35c1f77820b6f9a051d3f88aeec84842b62594158b560f85868e5cc6c1123e4b` |
| `static.log` | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct and read back actual yield sign and no-line/no-crosswalk site; save original view-ray stations and through-vehicle motion during crossing; implement finalizer and immediate-hazard review packet, exact positive/negative compatibility and independent delivery/comparison audits. CARLA motion and visibility follow CPU readiness.
