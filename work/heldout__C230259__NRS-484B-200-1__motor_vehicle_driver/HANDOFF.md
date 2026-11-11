# heldout__C230259__NRS-484B-200-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-200-1, cell: C230259, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C230259__NRS-484B-200-1__motor_vehicle_driver/assignment.json` (4cd5e091ff9c43386287635128c4d3602dff474fa0d99c22ae17de180f54864a).

Exact law text: Upon all highways of sufficient width a vehicle must be driven upon the right half of the highway, except as follows: (a) When overtaking and passing another vehicle proceeding in the same direction under the laws governing such movements; (b) When the right half of the highway is closed to traffic; (c) Upon a highway divided into three lanes for traffic under the laws applicable thereon; (d) Upon a highway designated and posted for one-way traffic; or (e) When the highway is not of sufficient width.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C230259__NRS-484B-200-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C230259__NRS-484B-200-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- right-half driving baseline on sufficient-width two-way highway
- overtaking/passing same-direction exception under governing passing laws
- right-half closure exception
- three-lane highway exception under applicable lane laws
- designated and posted one-way exception
- insufficient-width exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 right-half geometry CPU checkpoint

The frozen accepted-evidence inventory has zero recordings. `case-plan.json` now names seven planned exact cases and six comparisons for the right-half baseline, same-direction passing, right-half closure, three-lane highway, designated and posted one-way highway, and insufficient-width exception. Its earlier `branch_analysis` described overtaking-vehicle signaling from another law; this was corrected to the exact NRS 484B.200(1) alternatives. All cases remain unconstructed and no statutory exception is claimed proved.

`right_half_measurement.py` requires original 20 Hz ego body corners, map road center and traffic-direction tangent, and measured roadway width in `ego_road_frames.jsonl`. It reports the signed lateral extent of the whole vehicle body and whether it is wholly right, wholly left, or crosses the centerline. It uses the map traffic direction, not ego heading, so opposite travel directions map to the correct right side. `road_exception_context.json` must address each of the five exceptions; known true or false values need a separate source citation, and unresolved values remain null. There is no invented minimum legal highway width or legal right-half verdict. Native source capture, passing-law review, posted sign, closure and actual roadway geometry still require implementation.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `54fd8b4b4e163d7c663db98cd7d5bb00c9254612500ec402110d3c5e28a9e892`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C230259__NRS-484B-200-1__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `b1630d0221f815bdda083d847f7b9a94b8defa678bfe84d53d844972ec682ea4`). These exercise both traffic directions, centerline overlap, a cited closure, missing exception review, discontinuous original frames and degenerate tangent. They are source-shaped fixtures, not physical verification.

Next CPU work: Native map/body/roadway acquisition and one selected exact construction with controller, four source cameras and saved finalizer; then exact offline, positive/negative compatibility and saved-processing proofs, linked cases and fallback candidates, semantic proposals and independent audits. Keep `result.json` partial until the scoped strict gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C230259__NRS-484B-200-1__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result remains partial (`strict-gate.log`).
