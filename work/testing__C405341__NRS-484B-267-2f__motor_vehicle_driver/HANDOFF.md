# C405341 / NRS 484B.267(2)(f) CPU handoff

Status: partial while exact current-runtime proofs run. The frozen evidence inventory contains zero accepted recordings. No physical or legal acceptance is claimed.

The 2f clause requires qualifying flashing lights. It does not itself require a siren or front-visible red lamp; those inherited 1a prerequisites were removed.

Ten selected cases cover moving-unit approach and requested response, no response, distant/non-immediate approach, inactive and unqualified lights, officer direction, regulatory-official alternative, same-direction approach, visible hand-signal preparation followed by movement, and an approaching unit that then stops. Nine controlled comparisons hold all undeclared conditions fixed. The stopped alternative preserves the NRS 484B.607 referral without inventing its duties. Subsection 1 references 1a, 1b, and 1c; the assignment supplies 1c separately and this package does not infer missing 1a/1b duties.

`build_constructions.py`, `emergency_construction.py`, `runner.py`, `analysis.py`, and source packet validation implement ten exact source-gated constructions and saved original-frame measurements. `build_diagnostics.py` creates source-hashed synthetic diagnostics under this assignment; fixtures are software probes only. Ten primary and ten fallback `runtime.py offline` checks passed. Ten physical/lifecycle fixture checks passed. Four unit tests passed in `cpu-tests.log`.

Next: finish `prove_compatibility.py` v4 for every primary/fallback; run `prove_saved.py`, `prove_audits.py`, `build_queue_proposal.py`; run `worker_check.py --assignment testing__C405341__NRS-484B-267-2f__motor_vehicle_driver --complete --require-delivery-ready`, repair findings, then mark ready. All scratch is under `.runtime-work/c405341-2f/`.

Remaining local GPU checks: original Native authority, qualifying equipment/light use, visible hand signal and movement, both approach relationships, driver response, officer direction, full four-camera pixel visibility, and independent legal review of the referenced subsection.

## Exact selected identities

Cases:

- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__immediate_approach_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__immediate_approach_no_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__no_immediate_approach`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__lights_inactive`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__lights_unqualified`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__officer_directs_otherwise`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__regulatory_official_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__same_direction_approach_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__preparing_visible_hand_signal`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__stopped_referral`

Comparisons:

- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_immediate_approach_no_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_no_immediate_approach`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_lights_inactive`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_lights_unqualified`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_officer_directs_otherwise`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_regulatory_official_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_same_direction_approach_yield`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_preparing_visible_hand_signal`
- `testing__C405341__NRS-484B-267-2f__motor_vehicle_driver__yield_vs_stopped_referral`

## Exact CPU proof commands

Set `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c405341-2f/output-root"`, `TMPDIR="$PWD/.runtime-work/c405341-2f/tmp"`, and `PYTHONDONTWRITEBYTECODE=1` first.

```sh
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/build_diagnostics.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/build_constructions.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/build_semantic_proposals.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_offline.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_fallback.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_physical.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_compatibility.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_saved.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/prove_audits.py
.venv-cpu/bin/python work/testing__C405341__NRS-484B-267-2f__motor_vehicle_driver/build_queue_proposal.py
.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2f__motor_vehicle_driver --complete --require-delivery-ready
```
