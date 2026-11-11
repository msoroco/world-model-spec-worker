# heldout__C102304__NRS-484B-710__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-710, cell: C102304, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/assignment.json` (65306863f6f9c06d3529c3d84d4f9aa701426fcc3ee6e2c896ea225ff19f9966).

Exact law text: The driver of any motor vehicle other than an authorized emergency vehicle on official business shall not follow any fire apparatus traveling in response to a fire alarm closer than 500 feet or driving to or park such vehicle within 500 feet of fire apparatus which stopped in answer to a fire alarm.

Accepted recording summaries to review: 2; inventory `inputs/heldout__C102304__NRS-484B-710__motor_vehicle_driver/evidence.json` (5466012de98df865a29f340b00bd7381e260caea973095f5b84a308e2752699a). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and bound comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery audit remain to implement. A standalone source-recomputing comparison audit is now implemented but has not yet been bound to exact cases.

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

## Current CPU construction checkpoint

`fire_distance.py` measures the minimum distance between complete ordered Native ground-footprint polygons and separately records centre distance. It reads retained Native JSONL, binds the SHA256 of the original bytes, and rejects missing/invalid geometry, missing ticks, changed actor identities and missing source. `fire_branch.py` joins that measurement to retained frame/time-matched participant-state JSONL and reports active frames for traveling/following, stopped/driving-to, and stopped/parked alternatives. Traveling following uses footprint separation; stopped-apparatus alternatives use centre distance, per the assignment's distinct `rel.surface_gap` and `rel.centre_distance` observation terms. Driving-to requires measured closing centre distance across consecutive frames; merely moving near a stationary apparatus is rejected. It preserves alarm-purpose and authorized/official-business context as separately sourced premises, and reports below/at/above 500 ft samples with a 1e-6 ft floating-point reporting bin that has no legal meaning. Neither module gives a legal verdict. `fire_comparison_audit.py` independently checks a declared fixed/difference comparison, source hashes, 500 ft bin membership and the measurement recomputed from retained sources. It rejects stale hashes, missing sources, changed fixed conditions and a rehashed but altered measurement. Its CLI takes a JSON comparison specification and emits a JSON receipt; exact case specifications are pending construction. `tests/test_fire_distance.py`, `tests/test_fire_branch.py`, and `tests/test_fire_comparison_audit.py` cover these paths. Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C102304__NRS-484B-710__motor_vehicle_driver/tests -v`; `cpu-tests.log` exit 0, 15 tests, SHA256 85ee053312200e44380892483cf757b6f37a638dcfcb42a34fc9a39ff4970446. This is an implemented measurement and comparison component, not an exact-case finalizer or compatibility receipt.

Next CPU action: construct the at-500 ft traveling case and stopped apparatus driving/parking below/at/above cases, bind retained Native footprint and participant-state JSONL acquisition plus `fire_branch.py` to the saved finalizer, and test the first exact case through offline, positive/negative compatibility and saved processing. Preserve accepted 450/550 ft traveling evidence without replay. Then complete branch comparisons, exception case, three tested fallbacks per case, proposals and independent audits before the assignment strict gate.

## Current gates

`.venv-cpu/bin/python runtime.py preflight` passed with pinned Python and Lean 4.28.0; repository unit tests passed (6 tests). Assignment `worker_check.py --complete` passed static checks (`worker-check.log`). Assignment `--complete --require-delivery-ready` failed as expected with `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`). Batch strict gate has the same failure in `work/_shared/batch-strict-gate.log`; 49 of 51 assignments are still partial. These are unfinished CPU deliverables, not an external dependency.

This return checkpoint adds the retained-source comparison audit and four passing audit tests, bringing the assignment to 15 passing tests. The next CPU construction and proof action is recorded above; the assignment remains partial until its strict gate passes.
