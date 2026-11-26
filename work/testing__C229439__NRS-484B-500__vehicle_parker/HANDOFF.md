# testing__C229439__NRS-484B-500__vehicle_parker

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.500 — When official traffic-control devices are erected at hazardous or congested places, a person shall not stop, stand or park a vehicle in any such designated place.
Assigned branch(es): Parking within the designated place.
Cell: C229439 (road, park, parking_restriction_device); actor: vehicle_parker.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229439__NRS-484B-500__vehicle_parker --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

NRS 484B.500 covers stopping, standing and parking within a place designated by erected official traffic-control devices at a hazardous or congested place. `case-plan.json` now has five unselected planned cases and three comparisons for inside/outside footprint, three conduct types and hazardous/congested context. No frozen accepted recording exists. Generic restriction control does not establish device authority, designated extent or hazardous/congested character.

`parking_place.py` builds a vehicle footprint from a candidate pose and dimensions, checks all corners against a source-bound designated polygon and rejects a candidate that contradicts its requested inside/outside status. Its original-frame measurement binds vehicle/parker identity, official-device instructions and authority, place-character source, loading and officer/device direction sources, and ordered 20 Hz vehicle body footprints and speeds. It reports stationary wholly-inside frames using an engineering 0.1 m/s threshold but does not classify legal stop, stand or park. Six synthetic CPU tests pass, including negative official-authority, footprint-claim and loading-source checks.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `8816af8af5ce152d9fe1d004bd99369237b9d5eb6bb38a4ca3f61e366eb2f430` |
| `parking_place.py` | `1f5fc932c1ef5f5e5f4e0e423c0575f830177cd0ada3bc55ff4f23d562fee934` |
| `tests/test_parking_place.py` | `2b8fdd8394b711db6690f2b01e4ba16306418ddf4bca5c9de4261744bc3beeaf` |
| `preflight.log` | `988bcaba8a30f899f1a1f4abfbeedaf0c84a51167db547c7c3dce04a44405ec8` |
| `unittest.log` | `021064d0ea58e786e85ee531eb1c40454973b91a29fa306b05bc576416bf83f7` |
| `static.log` | `9b5a9eb0bdc78ec54747faf88a2bf1ba37ba4e01654b4b1466e5cfa4e285a75e` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `83bada72d627fcc35702239394a3aa248018a10786a5b982e16bc9b0da691e3b` |

Pinned preflight, six focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status; failed strict remains here and in `strict.log`, outside successful `result.json.tests` receipts.

Next CPU work: bind actual official device instructions, erection, authority and governed extent; review hazardous/congested physical facts and legal character separately; construct exact stop/stand/park capture and finalizer bundles, positive/negative compatibility, saved-only processing and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.

## 2026-11-25 CPU source and comparison checkpoint

The exact statute has no numeric distance or time boundary. The five planned cases cover the designated-place boundary, each named conduct, and the hazardous/congested alternatives; no accepted recording or judgment-range entry applies. The same cell remains the planned site. `parking_place.py` now requires an outside candidate to be wholly outside, rejecting straddling, boundary contact and an enclosing vehicle body. Its original-frame output separates overlap from wholly outside and reports contiguous stationary episodes without making a legal conduct finding. No legal duration threshold is inferred from the 0.1 m/s engineering observation.

`site_review.py` checks five original-source bindings (map, device, authority, extent and place facts), exact site identity, hashes, device instruction agreement and polygon agreement before a future Native runner uses a site. This is an integrity check; the current package contains no independently reviewed original site files and it makes no authority or hazardous-place finding. `comparison_audit.py` checks all three exact planned contrasts, rejects missing evidence, verifies measured inside/outside halt footprints, and checks fixed device, vehicle, cameras, duration and sources against declared differences. It is an independent CPU audit implementation for prepared measurement packets, not a receipt from a real recording or a substitute for the required delivery audit.

Focused command: `SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work .venv-cpu/bin/python -m unittest discover -s work/testing__C229439__NRS-484B-500__vehicle_parker/tests -v` (20 tests, exit 0; `unittest.log`). Scoped static command: `.venv-cpu/bin/python worker_check.py --assignment testing__C229439__NRS-484B-500__vehicle_parker --complete` (exit 0; `static.log`). Exact strict command remains `.venv-cpu/bin/python worker_check.py --assignment testing__C229439__NRS-484B-500__vehicle_parker --complete --require-delivery-ready`; it fails because the result is truthfully partial.

Remaining CPU work: connect reviewed source packet checks to a CARLA construction and controller; author five exact capture/finalizer bundles, camera and duration contracts, semantic proposals, diagnostic recipes, offline and positive/negative compatibility proofs, selected execution manifest, saved-only processing and independent delivery audit; bind the comparison audit to saved original attempts. Actual motion, pixels and site applicability are later local GPU checks. There is no demonstrated external blocker to the CPU work.
