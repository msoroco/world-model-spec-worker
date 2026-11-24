# testing__C157964__NRS-484B-257-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(1) — Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Yield sign; neither stop line nor crosswalk; nearest-view location..
Cell: C157964 (one_way_to_two_way_intersection, straight, police_officer); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 4. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C157964__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 4 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `yield_view.py` with four exact probes for this selected nearest-view yield-sign branch: slow/stop approaches, approaching/already-occupied through vehicle and active officer-control exception. The source-gated lazy constructor requests the route/reference/through phase and cleans actors on failure. Original measurement joins 900 frames and participant/source identities, measures first actual leading-body reference crossing, approach minimum speed, through center/min-vertex station and across-or-within history. Immediate hazard, right-of-way and exception applicability remain unresolved legal judgments.

Four focused CPU tests pass, including all four probes and negative hierarchy/control, missing original source, changed identity, absent crossing and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because the package truthfully remains partial. Diagnostic values do not satisfy the frozen judgment-range probe targets or establish physical sight. Additional statutory 257-1 hierarchy/exception branches, canonical capture/offline/compatibility, semantic proposals, independent saved delivery/comparison audits and physical source-backed site remain worker-owned CPU work.

Proof SHA256:

- `yield_view.py`: `fb0874d37af65536808776338ea76983920808812545eed7080dc75d975c3a73`
- `tests/test_yield_view.py`: `aa9ca8f0153802d97f08c42b479821354fe1a7ac8e34217e39528c18922ae327`
- `cpu-tests.log`: `2c61f0101510b355bde7d7a526021e4c40b7c72df3638c28edc4b1cbb0305c56`
- `cpu-preflight.log`: `5528f15c0f1710c4ab395a87272d10f64908567494ade60c77dea5d135e2bdf5`
- `cpu-static-check.log`: `1e88a34353c6e9b980ed94f5b5ed206cc52480e133f8e5efa9be6c0d4636f603`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
