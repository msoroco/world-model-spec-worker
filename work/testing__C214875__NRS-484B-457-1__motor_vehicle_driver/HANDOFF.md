# testing__C214875__NRS-484B-457-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

## 2026-11-27 14:12 UTC — selected right-curb boundary and source measurement

Five exact cases select parked 17, 18 and 19 inch right-wheel distance, 17 inch skew, and stopped at 18 inches; four comparisons isolate the statutory boundary, alignment and activity. `curb_geometry.py` requires six source-hashed original site records, affirmative highway/adjacent-curb/default-branch facts and reviewed absence of left-curb and angle-parking ordinance exceptions. It measures both right-wheel centers against the surveyed curb in meters converted to inches, and retains a 900-frame 20 Hz original wheel/activity join with source seal. Six focused CPU tests pass, including boundary, skew, stale source, ordinance uncertainty and degenerate geometry rejection. This is a partial CPU checkpoint: Native capture, selected construction bundles, semantic proposals, compatibility, saved-only processing and independent delivery/comparison proofs remain to be built. No physical or legal acceptance is claimed.

Exact law: NRS 484B.457(1); with 484B.457(2), 484B.457(3) — Except as otherwise provided in this section [(2) and (3) appended below], every vehicle stopped or parked upon a highway where there are adjacent curbs must be stopped or parked with the right-hand wheels of the vehicle parallel to and within 18 inches of the right-hand curb. Local authorities may by ordinance permit parking of vehicles with the left-hand wheels adjacent to and within 18 inches of the left-hand curb of a one-way highway. Local authorities may by ordinance permit angle parking on any highway, except that angle parking must not be permitted on any highway constructed and maintained by the Department of Transportation under the authority granted by chapter 408 of NRS unless the Department has determined that the highway is of sufficient width to permit angle parking without interfering with the free movement of traffic.
Assigned branch(es): Default right-curb position.
Cell: C214875 (residence_district, parallel_park, curb); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C214875__NRS-484B-457-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 14:17 UTC — construction, original readback and comparison checkpoint

`curb_construction.py` derives both right-wheel placement requests from source-reviewed curb tangent, roadway side and wheelbase; a bounded same-curb station fallback is tested for all five cases. `native_acquisition.py` records an immutable original attempt with 20 Hz frame/time/wheel/parking-control joins, all four synchronized original PNG streams, map identity checks and owner brake/cleanup on success or failure. `audit_original_attempt.py` independently verifies source hashes, frame continuity and camera archives; `audit_comparisons.py` checks all four planned pairs, fixed site/capture sources and observed distance/alignment/activity contrasts. `analysis.py` replays source-bound measurements without legal verdict. Five measurement contracts validate against pinned runtime; 13 focused synthetic tests pass, including stale source/camera and diagnostic-attestation negatives. `.venv-cpu/bin/python runtime.py verify --runtime runtime`, `runtime.py preflight` and scoped static worker check pass. The status remains partial: selected bundles, canonical proposals, offline/compatibility proofs, physical lifecycle and independent delivery audits are still CPU work.
