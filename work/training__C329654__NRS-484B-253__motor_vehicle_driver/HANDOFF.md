# training__C329654__NRS-484B-253__motor_vehicle_driver

Status: partial CPU construction checkpoint. Both exact inline cases are unselected drafts; no original Native, physical or legal outcome is claimed.

The exact statute requires a left-turning driver within an intersection to yield to an opposing vehicle within it or so close as to constitute an immediate hazard. After yielding and signaling when and as required, the driver may turn and the opposing drivers then owe the yield. The frozen witness focuses on conditional subsequent permission. Six accepted recording IDs are membership-only here; source-hashed equivalence has not been established and they are not proposed for replay.

`native/left_turn_request.py` generates two exact 600-frame, 20 Hz, 30-second authored requests with a fixed opposing conflict passage at frame 250. The yielded condition starts turning at frame 300 after that passage; the early condition starts at frame 180 when the opponent's engineered time to conflict is 3.5 s. The source meter requires frame/time joins, ego signal/intersection source and opposing actor source. Three negative checks reject absent opposing source, absent signal and forged original provenance. The time-to-conflict value is a diagnostic measure, not a legal immediate-hazard threshold.

`native/build_draft.py` authors two exact primary inline constructions with a 30-second duration and all four named source-camera contracts. Both pass pinned `runtime.py offline`. They remain unselected because actual Native capture, source-bound compatibility and saved processing are not implemented. `native/measurement-contract.json` maps all ten law-planning terms to the original sources required for later saved measurement.

Source/proof SHA-256:

- `native/left_turn_request.py`: `dcec87bd567f6e30599363fe80de126682e3854d5b0421fa79a05722ecf952dd`
- `native/left-turn-diagnostic-proof.json`: `bfbd5c4e832af77eb2bcf2c52552eb5e5703581c8a4e999a6aa4d421ee45075c`
- `native/measurement-contract.json`: `e16c0477aea1d38d2a81f2d1b8b6ed12782dfbb2c435c0c02b568b419eb22486`
- `native/draft-manifest.json`: `ca69afc852aa3819d0224a17a561cc78c9146b949335e3eebe85532ba0d1e85d`
- `native/condition_a-construction.json`: `85f4ce7f98304e4812bbc435c64c95a03336c569da3992b5dc23adffb7fffb60`; passing `native/condition-a-offline.log`: `283f3b8a18f569ffb026957796b125b7eeb90a45c7e54facbf2c76e2778ce864`
- `native/condition_b-construction.json`: `46ac35895c212caea1c6ca36a500914c96e9080e16fd4ca86c6ab34cf51bd01d`; passing `native/condition-b-offline.log`: `1dd9d2a89508041fb60e365c83d671f4018b61440b0831963c16ff561fead158`

Generated diagnostic rows and negative fixtures are under ignored `.runtime-work/c329654-left/`; offline materializations are under `.runtime-work/c329654-left-offline-a/` and `-b/`.

Passed commands:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C329654__NRS-484B-253__motor_vehicle_driver/native/left_turn_request.py prove --output .runtime-work/c329654-left
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C329654__NRS-484B-253__motor_vehicle_driver/native/draft-manifest.json --case training__C329654__NRS-484B-253__motor_vehicle_driver__selected_d457f261__condition_a --output .runtime-work/c329654-left-offline-a
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C329654__NRS-484B-253__motor_vehicle_driver/native/draft-manifest.json --case training__C329654__NRS-484B-253__motor_vehicle_driver__selected_d457f261__condition_b --output .runtime-work/c329654-left-offline-b
```

Next CPU work: implement connected Native intersection geometry, ego and opposing controllers, signal acquisition and four synchronized source cameras; bind original actor/map/frame readback to a saved finalizer. Run exact source-bound positive/negative compatibility and actual process-saved fixtures. Add physical-risk fallbacks, independent delivery and comparison audits, semantic proposals and current execution-manifest bindings. These remain worker-owned CPU tasks. Run scoped strict before any ready status; later physical review must establish actual motion, signal and hazard context.
