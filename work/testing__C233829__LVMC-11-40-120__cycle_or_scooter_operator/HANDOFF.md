# testing__C233829__LVMC-11-40-120__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.40.120 — Whenever a usable path for bicycles, electric bicycles, or electric scooters has been provided adjacent to a roadway, riders of bicycles, electric bicycles, and electric scooters shall use such path and shall not use the roadway.
Assigned branch(es): Adjacent designated path beside a road without a sidewalk..
Cell: C233829 (road_without_sidewalk, travel, cycle_path); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C233829__LVMC-11-40-120__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact law covers bicycle, electric-bicycle and electric-scooter riders when a usable path is provided adjacent to a roadway. `case-plan.json` now lists path and roadway routes for each covered device, plus an electric-scooter roadway case under an independently reviewed unusable-path context. Four comparisons isolate route choice for each device and path usability context for the scooter. These are planned constructions, not selected recordings; frozen accepted inventory is empty.

`path_route.py` selects a named route inside a source-bound designated-path or roadway polygon, requires adjacent-path and no-sidewalk cell context, and rejects a route that leaves its chosen facility. `path_observation.py` binds original trace and rider identity, designation, path condition/access sources and 20 Hz body-position observations. It retains usability as separate reviewed context and makes no legal conclusion. Seven synthetic tests exercise all three device classes, route creation, facility escape, roadway observation, missing access source and unresolved usability. Synthetic packets do not establish actual path provision or condition.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `40cc96da18c77077fb6fed4b5fc13a698e44cbe77e4c6036e6c7b0746bf9ec1a` |
| `path_observation.py` | `2340d4fc8d07a22082d99a82b9ea43c6cd99b981757e0377d0e570c29318d929` |
| `path_route.py` | `49560c496ca851307516e7edfd1bcf6efac32205ed511deabdbcd042d6b9b85f` |
| `tests/test_path_package.py` | `baa493561b552add6a7577948631bf095b78abf1181e4e0f41848a3b6d5ab3bf` |
| `preflight.log` | `b2b4e93b740f824f679991dc33038cb862b93dfa62280a89a648838579c63469` |
| `unittest.log` | `bef197a129cf63a2296a29a65dd8adf29895a38e276a494f9f99f96714a61381` |
| `static.log` | `fb2f582bd0d5a0e3e3fc3afe14bf057ae58887365463b3427be3c0bbbcf927ec` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `f5d3ca42d75fcd1938c0dc478faa6251a5404f60d728575cde72d3483230a6c6` |

Pinned preflight, seven focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status. `result.json.tests` contains only successful package-relative, exact-command receipts; the failed strict check is retained here and in `strict.log`.

Next CPU work: bind a real source map and adjacent designated-path authority; review actual condition, access restrictions, municipal jurisdiction and state-definition composition; implement executable exact-case bundles, original saved finalizer, positive/negative compatibility, saved-only processing and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
