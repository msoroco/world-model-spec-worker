# testing__C197786__NRS-484B-913__motor_vehicle_driver

Status: partial. Exact static check passed; strict delivery check failed because the package remains partial. No physical or legal verdict is claimed.

## Source and coverage

The frozen NRS 484B.913 text prohibits driving over an unprotected fire-department hose laid on a highway or private way/place for fire, alarm, or practice use without consent from the fire department official in command. The fixed C197786 cell is a private way, travel, fire-hose context with a human motor-vehicle driver. No accepted recordings are listed in the frozen evidence inventory. Witness source index 482 is conditional and requires independent proof of the hose, purpose, private access, protection, official status, consent, and actual passage.

[case-plan.json](case-plan.json) now has seven exact cases and six controlled comparisons: fire/no consent, fire/granted consent, fire/explicit refusal, protected hose, physical avoidance, alarm, and practice run. The private-way fixed layout excludes a highway variant at this cell. Each case has a concrete physical-risk assessment; fallback construction is still unimplemented and has not been claimed.

## CPU implementation and proof

[fire_hose_delivery.py](fire_hose_delivery.py) requires a hose-specific Native blueprint, spawns it lazily and verifies actor readback. Its saved checker requires sealed Native identity, original 20 Hz ego frames, actual hose segment, department affiliation, private-way context, qualifying purpose, human driver, protection arrangement, official identity/status and consent source/timing/scope. It derives segment crossings without assigning a legal verdict. Independent comparison logic rejects reused attempts, changed fixed road/vehicle/official context, changed undeclared conditions and missing contrast. [delivery_audit.py](delivery_audit.py) exposes the saved check as a CLI. These are worker-side checks, not canonical acceptance.

- `.venv-cpu/bin/python -m unittest discover -s work/testing__C197786__NRS-484B-913__motor_vehicle_driver/tests -v`: 9 tests pass; `cpu-tests.log` SHA256 `56286feccafc8578a38583994f3c580e7297db2a8ebeacf76a7b9ac0631c532b`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C197786__NRS-484B-913__motor_vehicle_driver --complete`: pass; see `cpu-static-check.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C197786__NRS-484B-913__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `Preparation acceptance failed: partial/missing packages remain`; see `cpu-strict-check.log`.

## Exact next CPU work

1. Create per-case configuration, runnable CARLA construction/ego controllers and measurement contracts for the seven IDs; test both crossing and avoidance geometry against verified Native hose readback. Confirm or provide a hose-specific blueprint/mesh construction path without substituting a marker for a hose.
2. Build case-specific source-hashed diagnostic recipes and run exact offline and positive/negative compatibility commands for every case and any justified fallback.
3. Author all canonical semantic proposals and index, source-bound finalization, exact execution manifest, saved-only processing receipts, delivery acceptance audits and independent comparison audit commands. Verify four-camera 20 Hz/decode requirements and failure rejection.
4. Rerun focused tests, the exact static check and the strict assignment gate. Mark ready only if strict passes.

No frozen input, runtime, or batch file was edited. No Git command was run.
