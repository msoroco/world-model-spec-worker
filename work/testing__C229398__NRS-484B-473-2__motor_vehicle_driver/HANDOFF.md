# C229398 NRS 484B.473(2) handoff

Status: `ready`, with `delivery_prepared` CPU scope. The selected original Native run remains source gated and has not occurred. This package makes no physical or legal acceptance claim.

## Coverage and source review

The exact law requires depressed or dimmed displayed lights for a lawfully parked vehicle at nighttime upon a highway when neither cowl nor parking lamps are used. The law supplies no numeric beam cutoff. The frozen `evidence.json` lists no accepted recordings, so no branch is reused. The six exact cases all start with `testing__C229398__NRS-484B-473-2__motor_vehicle_driver__`:

- `night_undimmed_no_aux` and `night_dimmed_no_aux` isolate displayed-light dimming.
- `night_undimmed_cowl` and `night_undimmed_parking` isolate the two auxiliary-lamp alternatives against `night_undimmed_no_aux`.
- `day_undimmed_no_aux` isolates nighttime; `unlawful_park_undimmed` isolates lawful parking.

The five controlled comparisons in `case-plan.json` hold the vehicle, original highway and curb geometry, capture profile and other declared conditions fixed. `comparison_acceptance.py` reopens each source and rejects a changed fixed condition. Curb, standing purpose, loading, traffic direction, safety zone, double parking and grade remain separate reviewed context; they are not inferred from the lamp setting. The supplied judgment-range file has no NRS-484B-473-2 key, so no numeric training bound is claimed for the light judgment.

## Executable preparation

`source_packet.py` requires a source-hashed, reviewed original packet with adjacent OpenDRIVE, highway, parking-lawfulness, nighttime, vehicle and lamp findings. `runner.py` checks that packet and the reviewed operator hash before importing CARLA. `parked_lamps.py` builds the route and lamp commands, then measures 900 original 20 Hz frames with observed speed and lamp readback. `native_acquisition.py`, `capture_seal.py` and `native_output_bridge.py` acquire and seal four synchronized original RGB streams, actor pose/body, original frame joins, restoration and owner release. `process_saved.py` finalizes without replay. `delivery_acceptance.py` and `comparison_acceptance.py` are independent saved-source audits. Beam aim stays an engineering measurement; legal judgment remains unresolved.

`execution-manifest.json` selects all six delivery cases. Every case has a primary and one tested fallback that changes only the source-gated approach offset from 12 m to 18 m. Its trigger is a failed measured parking approach or lamp-visibility target, never a desired legal outcome. Each exact construction is inline and SHA bound. The manifest includes 12 current-runtime offline receipts, 12 positive and missing-source compatibility receipts, six recorded-only saved-processing and feedback receipts, three physical protocol outcomes per case, six positive and negative delivery audits, and five comparison audits. `proposals/semantic-index.json` binds the six canonical proposal stages and five judgment observables. `queue-proposal.json` contains exact local dispatch commands for lead integration.

## Proofs and local execution

Run from the repository root with `SCENARIO_PIPELINE_OUTPUT_ROOT` and `TMPDIR` under `.runtime-work/`:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C229398__NRS-484B-473-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484B-473-2__motor_vehicle_driver --complete --require-delivery-ready
```

The current focused run passes 21 tests in `cpu-tests-final.log`; the exact scoped strict gate passes in `.runtime-work/c229398-output/strict-final.log`. Original local execution requires a reviewed source packet and operator module with hashes supplied through the four `SCENARIO_PARKED_LIGHT_*` environment variables in `queue-proposal.json`, plus the local CARLA Python, host, port and canonical job fields. Then independently review the actual parked motion, 900 frames, original lamp hardware/readback, four camera pixels, full video, physical completion and legal judgment before acceptance into `full-test`.
