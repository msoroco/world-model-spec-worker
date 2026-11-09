# C129731 / NRS 484B.407 handoff

## Scope

Two planned original recordings, one visible and one occluded 500-foot raw-ray circumstance, at the same curved/crested mountain-road OpenDRIVE map. Both use a low-speed three-point U-turn request, an approaching conventional car on the opposite Native lane, four 20 Hz cameras, 45 s of synchronized original frames, actual-body nine-ray visibility sampling from both approach directions, and saved-only finalization. Law/cell/actor are frozen. No Native run, pixel review, legal verdict, accepted recording, or canonical adoption is claimed. The 180 m and 200 m turn sites are engineering samples, not legal cutoffs.

## CPU proofs

- `python3.11 -m unittest discover -s work/testing__C129731__NRS-484B-407__motor_vehicle_driver/tests` passes 5 tests; log `cpu-tests.log`.
- `python3.11 runtime.py offline ...` passed for both primary and both fallback1 constructions. Exact commands and log hashes are in `execution-manifest.json`.
- `PYTHONPATH=runtime/scenario_pipeline python3.11 -m worker_exchange.atom_preflight --runtime runtime --config work/testing__C129731__NRS-484B-407__motor_vehicle_driver/config.json` passes for supported atoms.
- `runtime/scenario_pipeline/traffic_spec_adapter/adapter.py` explicitly puts `st.sight_distance` in `UNSUPPORTED_ATOMS`; `atom_preflight.py` rejects it as a Core required atom. The required law evidence remains in `visibility_history.jsonl` and `analysis-report.json` supplement, with legal meaning unresolved.
- The exact `runtime.py compatibility` command currently stops at `fixture_recipe.inspect`: `ValueError: Case fixture needs explicit source files`. A complete source fixture, pinned CPU packages and a working converter/validator are still needed. None is claimed.
- Python 3.11 is `/usr/bin/python3.11`, but it has no pip and cannot import numpy, shapely, networkx, Pillow, matplotlib or pydot.
- `inputs/coverage/branch-sources.json` and `inputs/coverage/candidate-cells.json` are absent from this export; the full-branch source-topic gate cannot be completed from them. The exact statutory text and witness are in the frozen assignment.

## Native queue after local integration

Set `CARLA_PYTHON`, `CARLA_HOST`, `CARLA_PORT`, `LIBRARY`, and `VALIDATOR` in the local operator environment. The following order is the planned recording order; these are preparation commands and have not been run. For each case, create a fresh `ATTEMPT` and separate `OUTPUT` path. Run owner release after Native exit and before saved processing.

### visible_curve

1. `"$CARLA_PYTHON" runtime.py capture --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__visible_curve --output "$ATTEMPT" --host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"`
2. If the declared heading-change failure trigger is met without collision/source loss, use a **new** attempt: `"$CARLA_PYTHON" runtime.py capture --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__visible_curve --candidate fallback1 --output "$ATTEMPT" --host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"`. Do not choose by desired legal outcome.
3. `"$CARLA_PYTHON" runtime.py owner-released --attempt "$ATTEMPT" --receipt "$ATTEMPT/owner-released.json" --acknowledge-owner-released` (operator attestation only).
4. `python3.11 runtime.py process-saved --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__visible_curve --attempt "$ATTEMPT" --output "$OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$ATTEMPT/owner-released.json"`
5. `python3.11 work/testing__C129731__NRS-484B-407__motor_vehicle_driver/delivery_audit.py --attempt "$OUTPUT/v0001/analysis" --case testing__C129731__NRS-484B-407__motor_vehicle_driver__visible_curve --output "$OUTPUT/v0001/source-audit.json"`

### occluded_curve

1. `"$CARLA_PYTHON" runtime.py capture --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__occluded_curve --output "$ATTEMPT" --host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"`
2. If the declared heading-change failure trigger is met without collision/source loss, use a **new** attempt: `"$CARLA_PYTHON" runtime.py capture --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__occluded_curve --candidate fallback1 --output "$ATTEMPT" --host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"`. Do not choose by desired legal outcome.
3. `"$CARLA_PYTHON" runtime.py owner-released --attempt "$ATTEMPT" --receipt "$ATTEMPT/owner-released.json" --acknowledge-owner-released` (operator attestation only).
4. `python3.11 runtime.py process-saved --manifest work/testing__C129731__NRS-484B-407__motor_vehicle_driver/execution-manifest.json --case testing__C129731__NRS-484B-407__motor_vehicle_driver__occluded_curve --attempt "$ATTEMPT" --output "$OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$ATTEMPT/owner-released.json"`
5. `python3.11 work/testing__C129731__NRS-484B-407__motor_vehicle_driver/delivery_audit.py --attempt "$OUTPUT/v0001/analysis" --case testing__C129731__NRS-484B-407__motor_vehicle_driver__occluded_curve --output "$OUTPUT/v0001/source-audit.json"`

## Native acceptance checks

Review the actual OpenDRIVE generated road and rendered mountain feature, body footprint within the turnout, other-car motion toward the turn, full reversal, any collision, both direction 500-foot rays (including blockers and route-limit unknowns), four original camera videos and their composed full-length video. Confirm the visible/occluded contrast in original pixels, not only ray metadata; sample the original footage for physical scene difference from accepted demo-train cases of the same law before dispatch. The fallback changes shared controller policy in both members. The saved audit checks source joins and raw-ray coverage only and explicitly does not accept physical completion or pixels. Native result and original video/Core evidence require independent local acceptance into demo-test and full-test.

## Limits

The clone contains 43 assignments; this handoff changes only this one. Batch-level branch review, ordered queue and local integration proof cannot truthfully cover the untouched 42. The pair is planned, not Native executed or video/Core accepted. The visual distinction and 500-foot physical sightline category remain unconfirmed until CARLA. No accepted demo-test/full-test recording is present in the assignment snapshot.

## Exact failed gates

- `python3.11 worker_check.py` stops at `runtime/scenario_pipeline/worker_exchange/physical_preparation.py` because the manifest has no `physical_preparation.receipt`; see `proofs/static-gate.log`. Physical fixture receipts are unclaimed.
- `python3.11 worker_check.py --complete --require-delivery-ready` stops first at the untouched C101303 assignment lacking `result.json`; see `proofs/strict-gate.log`.
- `python3.11 runtime.py compatibility ...` stops at `runtime/scenario_pipeline/worker_exchange/fixture_recipe.py:21` because the exact source recipe has no invented full Native fixture; see `proofs/fixture-blocker.log`.
