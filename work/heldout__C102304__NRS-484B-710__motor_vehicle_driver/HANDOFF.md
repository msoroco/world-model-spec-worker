# heldout__C102304__NRS-484B-710__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-710, cell: C102304, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/assignment.json` (65306863f6f9c06d3529c3d84d4f9aa701426fcc3ee6e2c896ea225ff19f9966).

Exact law text: The driver of any motor vehicle other than an authorized emergency vehicle on official business shall not follow any fire apparatus traveling in response to a fire alarm closer than 500 feet or driving to or park such vehicle within 500 feet of fire apparatus which stopped in answer to a fire alarm.

Accepted recording summaries to review: 2; inventory `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/evidence.json` (5466012de98df865a29f340b00bd7381e260caea973095f5b84a308e2752699a). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C102304__NRS-484B-710__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Existing evidence and exact gaps

The accepted 450/550 ft commanded following pair is source-bound in `case-plan.json.evidence_review`; it is limited to a traveling apparatus. Its reference check explicitly excludes the stopped branch. Commanded gaps are not substituted for the measured full-footprint gap. Alarm purpose and ordinary-subject status are synthetic premises.

Pending NRS 484B.710 alternatives: at-500 ft following boundary; driving to a stopped apparatus below/at/above 500 ft; parking within 500 ft of a stopped apparatus; and the authorized-emergency-vehicle-on-official-business exception. Build exact comparisons and four-camera saved-processing proofs before strict readiness.

## Full-text branch inventory (planning, unimplemented)

- traveling fire apparatus: follow at below/at/above 500 ft using measured footprint separation
- stopped fire apparatus: drive to within/at/outside 500 ft
- stopped fire apparatus: park within/at/outside 500 ft
- authorized emergency vehicle on official business exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.
