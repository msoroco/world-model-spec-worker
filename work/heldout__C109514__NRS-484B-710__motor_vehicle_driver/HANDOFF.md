# heldout__C109514__NRS-484B-710__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-710, cell: C109514, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C109514__NRS-484B-710__motor_vehicle_driver/assignment.json` (de7e87b9a58a07b73e09d602c4f7c12f4985702e6f0275c7403481245c223fe1).

Exact law text: The driver of any motor vehicle other than an authorized emergency vehicle on official business shall not follow any fire apparatus traveling in response to a fire alarm closer than 500 feet or driving to or park such vehicle within 500 feet of fire apparatus which stopped in answer to a fire alarm.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C109514__NRS-484B-710__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C109514__NRS-484B-710__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- traveling fire apparatus: follow below/at/above 500 ft
- stopped apparatus: drive to below/at/above 500 ft
- stopped apparatus: park below/at/above 500 ft
- authorized emergency vehicle on official business exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## Current evidence disposition

`evidence.json` contains no accepted recordings, so `case-plan.json.evidence_review` now records four source-cited gaps for the traveling, stopped-driving, stopped-parking and authorized-on-official-business branches. No C102304 accepted recording is claimed equivalent to this intersection cell. Next construct the primary following case with measured original-frame body separation, then run its offline, positive/negative compatibility and saved-processing proofs before expanding comparisons and fallbacks.

## Current gate

`.venv-cpu/bin/python worker_check.py --assignment heldout__C109514__NRS-484B-710__motor_vehicle_driver --complete` passed static checks (`worker-check.log`). Status remains partial because exact construction and CPU proofs have not been built. The current pinned runtime preflight passes; no dependency or tool blocker is claimed.

## 2026-11-11 construction continuation

`intersection_route.py` now selects a connected through-intersection Native waypoint chain with a junction between the two planned actors and an approximate 500 ft centre separation. It rejects absent junctions, discontinuity, ambiguous continuations and insufficient beyond-junction runout. This is a real route construction helper, not a flag asserting intersection presence. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C109514__NRS-484B-710__motor_vehicle_driver/tests -v` passes 3 geometry tests; `cpu-tests.log` SHA256 67981b35b2231c1146f7fc51e2ce549b40385c80094dd017513e4391ac0a9b9e. The first `__traveling_follow_500ft` exact case and its specific route risk are in `case-plan.json`. Relevance, template and intersection-specific binding drafts in `proposals/` pass pinned stage validation. The assignment checkpoint gate passes with truthful partial status.

Next CPU actions: integrate `intersection_route.select_intersection_route` with a C109514-specific runner/controller and four source cameras, then author raw footprint/state finalization and run the exact primary offline and positive/negative compatibility plus saved-only processing path. Only after that primary path passes, expand the 499/501 ft comparison, stopped drive-to/park triples, emergency exception, and each case's three risk-triggered fallbacks. Bind semantic cases, physical and delivery acceptance receipts, and independent comparison audits. Use `.venv-cpu/bin/python worker_check.py --assignment heldout__C109514__NRS-484B-710__motor_vehicle_driver --complete --require-delivery-ready` only after its own CPU proofs pass.
