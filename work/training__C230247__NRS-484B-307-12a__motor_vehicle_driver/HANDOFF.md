# training__C230247__NRS-484B-307-12a__motor_vehicle_driver

Status: partial. NRS 484B.307(12)(a) permits a driver facing a downward green arrow to drive in a lane over which it is displayed. The adjacent-lane comparison makes no prohibition claim. Frozen accepted evidence is empty.

## Exact selected CPU checkpoint

- `condition_a`: construction SHA-256 `658727c8a4bd79b8f71c73140ba504d820f19d57a099b9f349909ef963cefd67`; selected offline log SHA-256 `aa7dcc8376a7480d3035b178cb9c8b909271fb58332a3c4973fadafb9760266c`; positive/negative compatibility receipt SHA-256 `048dd9b684b048ccaae466045cc3b667275d78a2976c37f28e5c3216862639ad`. Target lane -1, under the arrow.
- `condition_b`: construction SHA-256 `9dc2e5b26d7522ef77f347cb574216d819faf49f69b42cd2fac1468d6e528c0f`; selected offline log SHA-256 `655ef259ff81d8f98dec95d923e976827e8bedf48ebfae3e45c5112b4fa7ef64`; positive/negative compatibility receipt SHA-256 `68f844b65722705d8e66bf8ca2ad88d1ebd1a641828f9a1d524672fc5ba5167d`. Target lane -2, adjacent to the arrow.

The two public compatibility commands passed selected measurement validation, original 600-frame saved finalization, Native attempt validation, Core conversion, Lean decoding, four-camera video decode and the negative that removes `native-signal-rows.jsonl`. Receipts are bound in `execution-manifest.json`. The fixtures are synthetic software diagnostics, not physical acceptance.

`native/signal_source.py` requires original map signal ID 100, exact lane-control actor role and a live `green_down_arrow` state. Generic traffic-light Green is rejected. `native-map-readback.xodr` is a separate acquired source. The saved finalizer checks the original frame, signal, map, actor, body occupancy and four-camera join. The current runtime source describes this signal but may not instantiate the exact overhead actor; acquisition fails closed if absent.

## Next CPU proof and local physical review

Six source-derived synthetic physical fixtures for complete/incomplete/missing motion and lifecycle order receipts now pass `physical_preparation.validate` for both selected cases. They claim no actual Native motion. Run `runtime.py process-saved` on each captured attempt after Native ownership closes, then independent delivery and comparison audits. After those CPU contracts pass, acquire original Native green-arrow pixels, verify official device authority and motor vehicle motion/cameras locally. Do not set ready without the exact assignment strict gate.

`TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230247 .venv-cpu/bin/python -B worker_check.py --assignment training__C230247__NRS-484B-307-12a__motor_vehicle_driver --complete --require-delivery-ready`
