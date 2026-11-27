# C230266 / NRS 484B.280(1)(a) handoff

Status: partial. The exact law requires the motor vehicle driver to exercise due care to avoid a collision with a pedestrian. The frozen witness requires a separate person-afoot path and an approach and separation observation window. No accepted recording membership is listed. Numeric encounter diagnostics and absence of contact do not settle due care.

## CPU construction and proof

- `native/due_care_meter.py` enforces a source-hashed, joined 600-frame / 20 Hz packet with distinct motor vehicle and pedestrian identities, independent path survey, measured pose/velocity/body dimensions, contact provenance and requested brake. It outputs first conflict, surface gap, contact, time to conflict, speed and deceleration diagnostics without a legal verdict. `native/measurement-contract.json` maps the source observations.
- `native/prove_due_care_meter.py` passed two synthetic 30-second comparisons and seven negative source gates. `native/due-care-meter-proof.json` SHA-256 `8a29c448bcf33d83eda2ee7846b72478c1991da30240d91896706caa7c2d862c`. These are software diagnostics, not original observations.
- `native/draft-primary/runner.py` is an unselected Native proposal with an independently specified walking path, a measured-distance brake request, original vehicle-attached collision event sensor, copied road survey, actor pose/velocity output, and synchronized `overview`, `ego_front`, `pedestrian_side`, `traffic_rear` cameras for 600 frames. Updated construction SHA-256 `948d1a98327e7bdc02cacb33762420cf1454652602930f172a3bd98048614ac8`; updated draft manifest SHA-256 `cea9848d37d0e8c6a792e7632fdfa27e047c751101a5ad4f1215a6e1945e4e73`. Pinned `runtime.py offline` passed four tests; `native/draft-primary/offline.log` SHA-256 `3428a73e044296e7d794c644bd48829b0077f6e3b0b0ce737a4986addd5580c6`.
- `native/saved_due_care.py` joins every original trace and frame-map identity, active contact sensor, collision events, road survey, fixed separate actor IDs and requested control into the source-hashed meter. The synthetic 600-frame source test passed one positive with a pedestrian contact event and four missing/mismatched source negatives; `native/saved-join-proof.json` SHA-256 `c9486588cc157e21117710b3588eef91671a75083b96f32043c06c14e82509e7`. This test does not observe Native motion or pixels.
- `native/selected_runner.py` and `native/build_selected.py` package the two exact selected comparison cases, condition A requesting measured-distance braking and condition B maintaining the request, with the same 20 Hz/30 s/four-camera setup. Inline constructions A/B SHA-256 `42808db32cee9729fb2ea89b2e22063ba811bc6f00717d43b176bea5ac65fb86` / `58e84c27a362a7c2669895fbb3adf2cf997f4071a01c7a6190dc7f8b8f1914fa`; their `native/selected-a-offline.log` / `native/selected-b-offline.log` SHA-256 `1518ab04fb224483d2f634d5f9345dc623cb5ef8594193842e647c0ed9f3be5c` / `92479a614e987b700141661d754dd32b8730082fbb7d707fbbfc3155dc4c90c2`, each four tests passing without CARLA.

## Remaining CPU work

The selected constructions and meter join are software checkpoints. Their finalizer still needs four-camera decode, canonical result and analysis report, and public fixture processing. Both cases need risk-based fallback candidates, positive/negative compatibility, process-saved checks, semantic proposals, independent delivery and comparison audits, and queue integration by the lead. Original Native placement, motion and pixels remain unobserved. Collision absence and numeric diagnostics do not decide statutory due care.

## Reproduction

```sh
.venv-cpu/bin/python runtime.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/native/prove_due_care_meter.py
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/native/test_saved_due_care.py
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/native/build_selected.py
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/selected-road-pedestrian-draft-manifest.json --case training__C230266__NRS-484B-280-1a__motor_vehicle_driver__selected_90e3f1aa__condition_a --output .runtime-work/c230266-selected-a-offline-v1
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C230266__NRS-484B-280-1a__motor_vehicle_driver/selected-road-pedestrian-draft-manifest.json --case training__C230266__NRS-484B-280-1a__motor_vehicle_driver__selected_90e3f1aa__condition_b --output .runtime-work/c230266-selected-b-offline-v1
.venv-cpu/bin/python worker_check.py --assignment training__C230266__NRS-484B-280-1a__motor_vehicle_driver --complete
```
