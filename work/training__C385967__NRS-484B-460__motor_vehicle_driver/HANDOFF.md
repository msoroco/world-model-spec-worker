# training__C385967__NRS-484B-460__motor_vehicle_driver

Status: partial CPU construction checkpoint. The two exact inline cases are unselected drafts; no original Native, physical or legal outcome is claimed.

The exact statute applies where official devices permit angle parking and requires a stopped, standing or parked vehicle to use the angle indicated to the curb or highway edge. The frozen witness is device-indicated parking angle. No accepted membership rows are available for reuse.

`native/angle_park_request.py` generates two exact 600-frame, 20 Hz, 30-second authored requests. The fixed official device indicates 45 degrees relative to the right curb and governs the same highway space in both conditions. The only comparison variable is requested at-rest vehicle heading: 45 versus 70 degrees. The source meter requires complete frame/time joins, device, curb, space and ego occupancy sources, and calculates angle only during 360 at-rest frames. It measures 0 versus 25 degrees absolute difference. Four negative diagnostics reject missing device, curb, space and forged original provenance. No legal angular tolerance is invented.

`native/build_draft.py` authors exact primary inline constructions with a 30-second window and all four named source-camera contracts. Both pass pinned `runtime.py offline`. They remain unselected because actual Native capture, source-bound compatibility and saved processing are not yet implemented. `native/measurement-contract.json` maps all seven law-planning terms to the original sources required for a later saved finalizer.

Source/proof SHA-256:

- `native/angle_park_request.py`: `8c9f3baea841e8e1f4c34bb3e97a65a9394132a19b78859d36603bd8eac9f9af`
- `native/angle-diagnostic-proof.json`: `7e562e3c4c322b04e0e3a8bf5c34f6e251414951202ac497ba71fd746f3e5710`
- `native/measurement-contract.json`: `ad151493d574c80bc7a53fe3289b710602b53b471c43f8e4d9ce9aed4a1aab3b`
- `native/draft-manifest.json`: `72470829d4de3b8ca26c1838fec92152adefdc3a0e477295dc85cc1fd058c848`
- `native/condition_a-construction.json`: `dc3d3e7512ec5c0b581b8cbf968d3b4bf11dfa24a261df0e200a36cceae73323`; passing `native/condition-a-offline.log`: `3a819c695519db692c5b7c91efd18ba22a49afee09c685b188ebc4b006528921`
- `native/condition_b-construction.json`: `a245fb0f416c3721ee54128bccdb39c3cf9bf2fed8235956a36c88f406a496f7`; passing `native/condition-b-offline.log`: `8ab737cef4dfbb70a9ee91ea0d89a0b12e7aa01c96a42997f57db42c49e8852c`

Generated diagnostic rows and negative fixtures are under ignored `.runtime-work/c385967-angle/`; offline materializations are under `.runtime-work/c385967-angle-offline-a/` and `-b/`.

Passed commands:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C385967__NRS-484B-460__motor_vehicle_driver/native/angle_park_request.py prove --output .runtime-work/c385967-angle
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C385967__NRS-484B-460__motor_vehicle_driver/native/draft-manifest.json --case training__C385967__NRS-484B-460__motor_vehicle_driver__selected_03f318de__condition_a --output .runtime-work/c385967-angle-offline-a
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C385967__NRS-484B-460__motor_vehicle_driver/native/draft-manifest.json --case training__C385967__NRS-484B-460__motor_vehicle_driver__selected_03f318de__condition_b --output .runtime-work/c385967-angle-offline-b
```

Next CPU work: implement a connected Native one-way road with an official angle-parking device, governed space and curb, an ego parking controller, and four synchronized source cameras. Bind original map/device/curb/actor/frame readback to saved at-rest measurements. Run exact source-bound positive/negative compatibility and actual process-saved fixtures. Add risk-based fallback constructions, independent delivery and comparison audits, semantic proposals and current execution-manifest bindings. These remain worker-owned CPU tasks; scoped strict must pass before ready.
