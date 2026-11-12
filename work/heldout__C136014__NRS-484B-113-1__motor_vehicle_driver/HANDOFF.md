# Handoff: heldout__C136014__NRS-484B-113-1__motor_vehicle_driver

## Scope and coverage

NRS 484B.113(1) governs backing only when it can be done with reasonable safety and without interfering with other traffic. The package keeps those judgments unresolved; no legal numeric threshold is invented. The nine exact selected cases cover clear/close traffic, steady/braking traffic, three rear spacing setpoints (8, 16, 12 m), and three other-traffic braking onset controls (frames 40, 120, 80). The source-bound seven-stage semantic draft and `case-plan.json` map both judgment phrases to these comparisons and original observation sources.

## Construction and CPU proof

`execution-manifest.json` selects all nine exact cases and three distinct risk-triggered fallback constructions per case. Each has a Native CARLA runner, four named synchronized original camera streams, retained backing history, measurement finalizer and contract, diagnostic recipe, and source-bound acquisition description. All 36 candidate bundles passed exact offline, positive/negative software compatibility, and positive/missing-source saved-only processing with the pinned CPU runtime and Lean decoder. Compatibility receipts, command logs, and saved proof hashes are bound in the manifest.

`physical_fixture.py` exercised complete, incomplete and missing-evidence outcomes for each case. `lifecycle_fixture.py` verified capture, encoder, settings restoration, owner release and saved-only processing order. `delivery_audit.py` independently checked both participants, source time joins and four full video decodes, and rejected a missing backing history. `comparison_audit.py` and `sweep_comparison_audit.py` independently checked the source joins and fixed grid controls, including swapped-source rejection. These are CPU fixtures and protocol proofs. The spacing fixture reproduces all three spacing setpoints; the interference fixture measures braking onset at frame 1 for all three requested onset controls, marks the requested target missed, and makes no physical realization claim. Native capture must determine whether the controls produce the requested onset and whether physical motion and original pixels meet acceptance.

Eight unit tests pass in `cpu-tests.log`. The scoped strict gate passes:

```sh
.venv-cpu/bin/python worker_check.py --assignment heldout__C136014__NRS-484B-113-1__motor_vehicle_driver --complete --require-delivery-ready
```

`result.json` declares `delivery_prepared` and provides the first canonical exact GPU command. This is CPU delivery readiness, not physical or legal acceptance. The later delivery operator must use actual Native recordings, full four-view original decodes, participant/time joins and measured maneuver completion to accept or reject each case.

## 2026-11-12 proof-preserving return compaction

Four root offline logs with the same SHA-256
`c6352adff70a6982c739a1cd77bbb43d2425eefd2dc2112b92b0ceebf2a6ca31`
were consolidated into retained `primary-nine-offline.log`:
`fallback1-nine-offline.log`, `fallback2-nine-offline.log`,
`fallback1-offline.log` and `fallback2-offline.log`. The manifest paths for the
two bound fallback receipts now point to the byte-identical retained log; the
other two were unbound historical copies. The assignment-scoped strict gate
still passes. This frees return slots without changing any proof bytes.

Two zero-byte root compatibility logs, `fallback2-compat.log` and
`fallback3-compat.log`, were likewise consolidated into byte-identical
`primary-nine-compat.log` (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
Manifest log paths were updated and the scoped strict gate still passes.

Two more byte-identical zero-byte nested compatibility logs for
`reverse_close_traffic_steady` (fallback2 and fallback3) were consolidated into
the same retained root log, with manifest paths rebound. The scoped strict
gate still passes; no compatibility receipt or negative log was removed.
