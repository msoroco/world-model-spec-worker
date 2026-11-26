# testing__C24823__NRS-484A-450-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484A.450(3) — The driver of a vehicle approaching a yield sign if required for safety to stop shall stop before entering the crosswalk on the nearest side of the intersection or, if there is no crosswalk, at a clearly marked stop line, or if none, then at the point nearest the intersecting highway where the driver has a view of approaching traffic on the intersecting highway.
Assigned branch(es): Conditional stop at nearest point with a view.
Cell: C24823 (blind_intersection, travel, yield_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C24823__NRS-484A-450-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The statutory stopping reference is the nearest crosswalk, otherwise a clearly marked stop line, otherwise the nearest point to the intersecting highway with a view of approaching traffic. Stopping is conditional on safety necessity. `case-plan.json` has five planned exact cases and three comparisons covering the fallback location, an earlier obscured stop, stop-line and crosswalk priority, and a separately reviewed no-stop necessity context. No accepted recording exists in the frozen inventory; these are unselected constructions.

`yield_site.py` requires source yield-sign governance, eligible vehicle and qualifying highway identity. For the blind fallback branch it requires constructed occluder rectangles, driver-viewpoint candidates, approaching-traffic sight targets and the intersecting-highway boundary. It computes geometric sight rays, then chooses the nearest candidate with an unobstructed ray. This is an engineering construction; the source driver viewpoint, whether a view is adequate, and stopping required for safety remain independent reviews. Six synthetic CPU tests cover the fallback, crosswalk and stop-line priority, no-view and missing-occluder rejection, and control mismatch.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `f288c7f39914cebe745ee9b6c52a8696c334a599b812436d97ed3d125472da6a` |
| `yield_site.py` | `50a1008c7d7eb3c431ee74a19a5a9fac46df1f24b87439cbb7978f3222858ecb` |
| `tests/test_yield_site.py` | `2faee1334c0ad11ebbca36c3b10980a41c3abece6295ed7b3e839ed15e5e9488` |
| `preflight.log` | `3946894b4ba0ea233b8a29a510f78ca53062f787c01b4bdc3bd9f673310e37a7` |
| `unittest.log` | `c4cb30d4ca4045697f1f2049a0b40e29722be7405103fc3f9e2e174f9d893ec8` |
| `static.log` | `a96f74002126ebaa38a0ade2336ad0d75605a96f182539c75613780cbae431e8` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `95f700c1e9f0c15f19c1776ad75c80b3b9a98a964bfcfef5b04b491e94a6cb06` |

Pinned preflight, six focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status; the failed check is recorded here and in `strict.log`, outside `result.json.tests`. The latter contains only successful package-relative exact-command receipts.

Next CPU work: bind the actual map, crosswalk/line inventory, occluder and driver sight sources; implement original stop-position/velocity finalizer, separately review safety necessity, construct all exact bundles and positive/negative compatibility, and prove saved-only processing and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.

## 2026-11-26 selected CPU delivery preparation

Five exact cases are selected in `case-plan.json` and `execution-manifest.json`: `fallback_nearest_view_stop`, `fallback_earlier_obscured_stop`, `marked_line_stop`, `nearest_crosswalk_stop`, and `no_safety_stop_required`, each prefixed by this assignment ID. Three controlled comparisons remain `nearest_view_vs_earlier_obscured`, `stop_reference_hierarchy`, and `conditional_safety_necessity`. No accepted original recording is present in the frozen inventory. The source law makes stopping conditional on safety necessity and orders references as nearest-side crosswalk, then clearly marked stop line if no crosswalk, then nearest point with a view of approaching traffic if neither exists. The geometric selector does not define a legal view or safety cutoff.

`yield_source.py` requires an exact independently reviewed original map, yield-site packet, seven source-hashed statutory records, a source-selected yield-sign actor, constructed occluder actor with corresponding geometry, source-positioned approaching-traffic motor vehicles with nonzero motion, an original route, and four camera poses. `native_yield_entry.py` constructs the sign, ego vehicle, occluder and approaching traffic, reads back occluder bounds, sign and traffic actor identities and positions, captures 900 original 20 Hz body, speed, control, traffic and four-camera samples, and restores the world/owner. `yield_measure.py` and `analysis.py` preserve source hashes and original frame/time joins, report the selected reference, pre-entry stop samples and traffic displacement, and leave original driver perception, safety necessity and legal assessment unresolved. The 0.1 m/s stop-sample threshold, 1.5 m controller brake target, 1 m occluder readback tolerance and 1 m traffic displacement requirement are engineering diagnostics only.

All five cases have current source-hashed diagnostic recipes, selected-requirement measurement contracts and primary plus one bounded throttle fallback. Ten exact offline and positive/negative compatibility receipts are indexed in `cpu-offline-proofs.json` and `cpu-compatibility-proofs.json`. Five three-outcome physical/lifecycle receipts are `physical-<case-suffix>-receipt.json`. Ten original-preserving saved-only positive/missing-site proofs are indexed in `cpu-saved-proofs.json`. Five independent positive/negative delivery proofs are indexed in `cpu-delivery-proofs.json`; three source-fixed comparison audits are in `comparison-proof-index.json`. These are CPU software fixtures only. `proposals/semantic-index.json` binds the source-gated semantic stages. `gpu-queue-proposal.json` provides five ordered case commands and three comparison commands for lead integration; local original source packet remains a required input.

Resume or recheck with `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c24823/output TMPDIR=$PWD/.runtime-work/c24823 PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C24823__NRS-484A-450-3__motor_vehicle_driver --complete --require-delivery-ready`. The prior partial status above is historical; current `result.json` is the authoritative status after the scoped strict gate. Physical CARLA motion, actual pixels and independent legal/source review remain future local checks.
