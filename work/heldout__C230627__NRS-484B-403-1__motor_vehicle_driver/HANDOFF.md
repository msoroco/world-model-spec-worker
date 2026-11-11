# heldout__C230627__NRS-484B-403-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-403-1, cell: C230627, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/assignment.json` (50905fa419a36c03cda9118e08894a85c86c7ab9e4a30c102c73d7777c2aa140).

Exact law text: A U-turn may be made on any road where the turn can be made with safety, except as prohibited by this section [NRS-484B-403-2, NRS-484B-403-3] and by the provisions of NRS 484B.227, 484B.363 and 484B.407 [NRS-484B-227-1, NRS-484B-363-3, NRS-484B-407].

Accepted recording summaries to review: 0; inventory `inputs/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- U-turn with physical safety judgment retained
- prohibition under NRS 484B.403(2) and (3)
- prohibition under NRS 484B.227
- prohibition under NRS 484B.363
- prohibition under NRS 484B.407

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 U-turn source measurement checkpoint

The frozen evidence inventory contains zero accepted recordings. `case-plan.json` now plans seven exact cases and six comparisons for whole-maneuver clearance and each of the five cited prohibitions. These are unconstructed cases, and the cross-reference conditions remain separately sourced questions rather than asserted legal conclusions.

`u_turn_measurement.py` joins original ego and surrounding participant bodies, yaw and participant speeds at 20 Hz. It reports the first measured heading-change frame, net heading change, minimum sampled body gap over the whole recorded maneuver, and each participant's minimum sampled acceleration. Roles such as oncoming and following need an explicit source citation. `u_turn_context.json` must address all five cited prohibition IDs, keeping unknown applicability null and requiring citations for known values. A 0.5-degree yaw change locates an engineering event onset; it is not a legal U-turn or safety threshold. Legal safety and prohibition judgments remain null. Native acquisition, complete sight-distance source and actual actor braking/visibility remain to implement.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `7d74db1a129fa435559368006f751ade4ebf645660be2d198012e217ecb3a130`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C230627__NRS-484B-403-1__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `79ed4d083b416e7df6a771151586495373262830dc5f17b698c1884b57bfb69c`). They reject missing prohibition context, uncited known applicability, discontinued frames, changed actor identities, missing original motion and nonfinite participant speed. The fixture does not prove physical U-turn safety or any cited prohibition.

Next CPU work: Native U-turn geometry/controller and surrounding-user acquisition, shared sight-distance source and four cameras, saved finalizer, exact offline/positive-negative compatibility/saved-processing proofs for a primary case; then the other cases, fallback candidates, proposals and independent audits. Keep `result.json` partial until the scoped strict gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C230627__NRS-484B-403-1__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result remains partial (`strict-gate.log`).
