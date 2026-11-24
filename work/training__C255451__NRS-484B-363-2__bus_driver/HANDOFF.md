# training__C255451__NRS-484B-363-2__bus_driver

Status: partial CPU construction checkpoint. The exact drafts are unselected; no original Native, physical or legal result is claimed.

The express 25 mph rule applies within a designated school crossing zone subject to four distinct exceptions: school not in session; the half-hour post/pre-operation period; an operational beacon with nonflashing yellow lights during class hours; and a nonbeacon zone whose sign says the limit is inactive. The beacon definition requires a sign and two or more alternating yellow lights. The frozen selected witness is a motor bus in a school crossing zone with children. No accepted membership rows are available for reuse.

## Current exact construction

`native/school_zone_request.py` generates 600-frame, 20 Hz, 30-second authored bus requests for both exact planned IDs. The fixed zone lies between x=100 m and x=200 m with two child actor requests. The comparison changes only requested bus speed: 20 mph versus 30 mph. The source meter requires complete frame/time identity, motor bus, school crossing zone and child sources, then reports in-zone frames and frames above the law's express 25 mph speed. It measured 0/224 above-limit zone frames for the lower-speed request and 149/149 for the higher-speed request. Four negative diagnostics reject absent bus, zone or child sources and forged original provenance. These rows are authored diagnostics, not original CARLA velocity, signed-zone pixels, school calendar or legal applicability.

`native/build_draft.py` authors two exact inline primary constructions with a 30-second window and four named source-camera contracts. The pinned `runtime.py offline` command passed for each. They remain unselected because original Native capture, source-bound compatibility, saved processing and independent audits are not yet implemented. `native/measurement-contract.json` maps all seven summary terms to original sources and explicitly separates the four exception contexts from speed measurement.

Source/proof SHA-256:

- `native/school_zone_request.py`: `60ea3fff894f467d6ebda0d14c39326e9364bdaa45f4381564ab0d43af90c7b7`
- `native/zone-diagnostic-proof.json`: `b59765ad03a85d547ef0fdadb6094de34a6ecbce8e249563058822ad1fcd4aca`
- `native/measurement-contract.json`: `6737ff295c9f478e3272a71dc654f828476d8fb42027a68cd3646b18b0bbd230`
- `native/draft-manifest.json`: `82c011a24678a53a284174a92823df03976e88b10cc3117d75d47dc2788b0b3c`
- `native/condition_a-construction.json`: `9b88341515d37938be62aec4f3b4f4bad9b3f99ac8abb47dd769227fc93dc7be`; passing `native/condition-a-offline.log`: `d3d6e2c9d4f58215561a0a52ea261cb6652354eb356dcf97f66e3e0c32aa9563`
- `native/condition_b-construction.json`: `216c442a806ad1f59b7757b78a9997ae64460d427d3dd756554fc1c54efcb51b`; passing `native/condition-b-offline.log`: `c83b145b7c124843a22ee78a633238ce288b8bfc81608efc3942d958896954f2`

Generated diagnostic rows and negative fixtures remain under ignored `.runtime-work/c255451-zone/`; offline materializations are under `.runtime-work/c255451-zone-offline-a/` and `-b/`.

Passed commands:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C255451__NRS-484B-363-2__bus_driver/native/school_zone_request.py prove --output .runtime-work/c255451-zone
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C255451__NRS-484B-363-2__bus_driver/native/draft-manifest.json --case training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__condition_a --output .runtime-work/c255451-zone-offline-a
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C255451__NRS-484B-363-2__bus_driver/native/draft-manifest.json --case training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__condition_b --output .runtime-work/c255451-zone-offline-b
```

## Next CPU work

Implement a connected signed school crossing zone with bus and child Native actors, four synchronized source cameras, original actor velocity, sign/beacon state and civil-time source acquisition. Add a saved finalizer that derives zone occupancy and speed from original sources, with separate source-backed handling for each exception and the beacon definition. Run exact source-bound positive/negative `runtime.py compatibility` and actual `process-saved` fixtures. Expand the branch matrix for each distinct exception, test risk-based fallbacks, independent acceptance and comparison audits, semantic proposals and execution-manifest bindings. The above diagnostic is not a substitute for these worker-owned CPU tasks. Run scoped strict only after they pass.
