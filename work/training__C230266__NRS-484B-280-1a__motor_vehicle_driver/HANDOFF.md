# C230266 / NRS 484B.280(1)(a) handoff

Status: partial. The exact law requires the motor vehicle driver to exercise due care to avoid a collision with a pedestrian. The frozen witness requires a separate person-afoot path and an approach and separation observation window. No accepted recording membership is listed.

## CPU construction and proof

- `native/due_care_meter.py` enforces a source-hashed, joined 600-frame / 20 Hz packet with distinct motor vehicle and pedestrian identities, independent path survey, measured pose/velocity/body dimensions, contact provenance and requested brake. It outputs first conflict, surface gap, contact, time to conflict, speed and deceleration diagnostics without a legal verdict. `native/measurement-contract.json` maps the source observations.
- `native/prove_due_care_meter.py` passed two synthetic 30-second comparisons and seven negative source gates. `native/due-care-meter-proof.json` SHA-256 `8a29c448bcf33d83eda2ee7846b72478c1991da30240d91896706caa7c2d862c`. These are software diagnostics, not original observations.
- `native/draft-primary/runner.py` is an unselected Native proposal with an independently specified walking path, a measured-distance brake request, actor pose/velocity output, and synchronized `overview`, `ego_front`, `pedestrian_side`, `traffic_rear` cameras for 600 frames. `native/unselected-road-pedestrian-construction.json` SHA-256 `9c6420a61410d573bb64c834a1488680cb6605370d944c6c71c537948bb2d05a`; its unselected manifest SHA-256 `43709077895e2e623a5185e2e64e51f0e52703f60ec5f63d5a1e657c0fbc8672`. Pinned `runtime.py offline` passed four tests; `native/draft-primary/offline.log` SHA-256 `8d80340c2ad9216309c2238c132914aae1c36c409e7237560ea45f41b778c7ae`.

## Remaining CPU work

The draft capture still needs original contact event collection and a saved-source finalizer that joins its JSONL trace, frame map, contact stream and camera videos into the meter packet. The planned two exact selected comparison cases need construction, controlled comparison, risk-based fallback candidates, positive/negative compatibility, process-saved checks, semantic proposals, independent delivery and comparison audits, and queue integration by the lead. Original Native placement, motion and pixels also remain unobserved. Collision absence and diagnostic numeric values do not decide statutory due care.

## Reproduction

```sh
.venv-cpu/bin/python runtime.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/native/prove_due_care_meter.py
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/native/build_draft.py
.venv-cpu/bin/python runtime.py offline --manifest work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/draft-road-pedestrian-manifest.json --case training__C230266__NRS-484B-280-1a__motor_vehicle_driver__probe_1 --output .runtime-work/c230266-nrs280-1a-draft-primary-v2
.venv-cpu/bin/python worker_check.py --assignment training__C230266__NRS-484B-280-1a__motor_vehicle_driver --complete
```
