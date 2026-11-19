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

### 2026-11-15 proof-preserving return compaction

Removed 70 byte-identical case logs and rebound their exact references in `execution-manifest.json` to retained identical bytes. The assignment-scoped `--complete --require-delivery-ready` gate passed before and after compaction. Result remains ready; no source proof was weakened.

2026-11-18 onset-sweep construction inspection: the three returned Native runners schedule braking after 40, 120 and 80 iterations respectively and each requests 160 frames. Their current CPU diagnostic generators retain only nine joined evidence, graph, trace, body and video frames, with braking measured at index 1 in all three. The fixture cannot prove the frozen distinct onset setpoints. Extend each source-joined synthetic diagnostic and media to cover at least the latest 120-frame onset within the returned 2 MiB per-file limit, then rerun all affected exact compatibility, saved processing, physical/lifecycle and independent sweep comparisons. Keep partial until that source-bound evidence and the scoped strict gate pass.

2026-11-19 return-cap preservation: historical `cpu-tests.log` and its result test record were losslessly archived at `work/_shared/c147331-turn-return-cap-archive.json`. Restore and hash-check before relying on that historical test. Current package remains partial.

2026-11-19 return-cap preservation: historical unreferenced `lifecycle_fixture.py` was losslessly archived in `work/_shared/c147331-turn-return-cap-archive.json`; restore and hash-check it before reuse. This package remains partial.

## 2026-11-19 current onset-sweep completion

The three interference-onset exact diagnostics now contain 160 consecutive, source-joined 20 Hz frames and four decoded 160-frame camera streams. A shared explicit `onset-evidence.jsonl` retains the original-shaped RGB packet for every frame; the generator source and recipe hashes are refreshed. The synthetic other-traffic speed changes first occur at frame indices 40, 120 and 80 respectively, matching the frozen setpoints. These data are diagnostic fixtures, not Native observations or physical/legal acceptance.

All 12 affected exact primary/fallback current-runtime compatibility runs pass, including each missing `backing_history.jsonl` negative. All 12 positive and 12 missing-source saved-only processing runs pass their expected paths and preserve original sources. Combined per-case saved proof logs are hash-bound in `execution-manifest.json`. Nine refreshed synthetic physical outcomes cover complete, incomplete and missing evidence, and three refreshed lifecycle proofs check capture, encoder closure, restoration, release and saved-processing order. `delivery_audit.py` independently verifies both participants, 160 joined frames and full four-view decodes for each onset case; it confirms fixed sweep conditions and rejects a swapped case. Eight unit tests pass.

Current execution manifest SHA-256 `8b3cc7b9f117819645e36d8eb2de8b6c6c889f6160c6e88a9d59842b1154248c`; `result.json` SHA-256 `754c7ff7f7b566d50eb6fd674c56c6016474ab1c511f7abe6d08e3391a26d1eb`. `execution_manifest.validate`, `package_compatibility.check_receipts`, and assignment-scoped `worker_check.py --complete --require-delivery-ready` pass. The ignored strict log is `.runtime-work/c136014-onset-scoped-strict.log`, SHA-256 `3f8642b9cf9918cf674e8daf01e5e6142b5919b047c7d0077328f9fc73c98330`. `result.json` is now truthful `ready` / `delivery_prepared`. Actual motion, source pixels, and legal judgments remain for the local delivery operator.

The return still has 10,200 files with no file over 2 MiB. Two unreferenced historical root negative logs were losslessly archived in `work/_shared/c147331-turn-return-cap-archive.json` to restore current lifecycle and CPU test evidence. The historical root `fallback1-saved-proof.log` was likewise archived to make room for the shared onset evidence source. No frozen input, runtime file or batch file was edited.
