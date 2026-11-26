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

## 2026-11-25 exact diagnostic construction and physical audit checkpoint

`build_diagnostic_bundles.py` generated `diagnostic-execution-manifest.json` and seven inline `cases/<short-id>/construction.json` bundles for the seven plan cases. Each contains an exact law/cell/actor/case configuration, four 20 Hz camera views, a source-gated Native entrypoint, and a bundle test. The entrypoint requires a reviewed original packet with independently hashed private-way, hose, incident, official, consent, and vehicle sources; checks a hose-specific blueprint ID, command status, timing/scope of positive consent, and crossing versus avoidance route geometry; then requires an original Native adapter and calls `construct_hose` for actor spawn and readback. These diagnostic bundles claim neither physical acceptance nor legal judgment. They do not yet implement a complete local Native adapter or selected production manifest.

All seven exact `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C197786__NRS-484B-913__motor_vehicle_driver/diagnostic-execution-manifest.json --case <exact ID> --output .runtime-work/hose-913-offline-<short-id>-v3` checks passed with `HOSE_SCRATCH_ROOT=$PWD/.runtime-work/hose-913-scratch`. Per-case command output and hash are recorded in `result.json`; generated test trees remain under `.runtime-work/`.

`fire_hose_delivery.body_over_hose_frames` now requires 900 original 20 Hz body footprints and returns original frames where the polygon intersects or contains the actual hose segment. `delivery_audit.py --require-complete-body --expected-passage cross|avoid` independently hashes and reads the Native JSONL frame source, joins it to the inline measured rows, and rejects a crossing/avoidance mismatch. This supplements the earlier centerline diagnostic. The focused suite now passes 11 tests, including source-hash, missing-footprint, incomplete-history and negative passage checks. It uses only `.runtime-work/` scratch.

Remaining CPU construction is the complete local Native adapter and camera/trace acquisition, selected delivery manifest, source-hashed per-case diagnostic compatibility fixtures with positive/negative receipts, semantic stage proposals, recorded-only processing and canonical delivery/comparison receipt bindings. The specific original source packet and hose blueprint are also absent from the provided inputs; no exact-case capture or physical completion can be asserted. Preserve `result.status=partial` and continue these CPU items before the strict assignment gate is reconsidered.

The semantic item above is now implemented: `build_semantic_proposals.py` writes nine draft canonical stages under `proposals/`, including exact law quote, source-gated hose/incident/official/consent judgments, seven selected cases and a shared baseline. `validate_semantic.py` runs the pinned runtime stage validator against the exact frozen assignment and current diagnostic manifest; it passed with seven selected cases and nine stages (`cpu-semantic-validation.log`). All seven inline constructions now contain the identical canonical recording description, and their v4 pinned offline runs passed. Remaining CPU work is the local Native adapter, positive/negative compatibility, selected manifest, saved processing and delivery/comparison bindings. Draft semantic validation does not establish original source evidence.

The v6 exact bundles strengthen source custody: each of the six reviewed inputs must be a distinct hash-pinned JSON file whose content equals the corresponding claimed site, hose, incident, official, consent or vehicle facts. The complete-body delivery audit applies the same distinct source-content join to the six saved context files, separately from the 900-frame Native JSONL hash/content join. The negative focused test changes a claimed hose-protection fact without changing its source; the audit rejects it. All seven v6 offline checks and 11 focused tests pass. Earlier v4 receipt paths in this file are historical; `result.json` carries current v6 hashes.
