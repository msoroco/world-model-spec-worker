# NRS 484B.410 at C227853: CPU checkpoint

Frozen actor/cell: `motor_vehicle_driver`, `road` / `depart_parked` / `curb`. The witness targets starting a parked vehicle on a highway. The statute also covers starting a stopped or standing highway vehicle and entering a highway, and excepts stopping, standing or parking where no parking is permitted. The words “unless and until” require facts available before the movement begins. No accepted recording is supplied. `case-plan.json` retains the full exact text and alternatives.

## Constructed and checked

- `native/geometry.py` authors a 160 m travel lane and curbside shoulder. `native/runner.py` surveys those lanes, starts an initially resting ego from the shoulder, and moves a nearby traffic vehicle. The ego policy is identical in both cases; only the traffic vehicle's initial position differs. Four original 1280×720 FFV1 camera streams, 600 frames at 20 Hz, original `FrameMap`, actor footprint/velocity traces and world restore/cleanup are coded. No Native execution or physical curb/pixel observation occurred.
- `build_draft.py` binds clear-traffic `controlled_1` and closer-traffic `controlled_2` primary constructions in `draft-departure-manifest.json`. Their construction SHA-256 values are `66fdca9253274a940df2efa15cb8279c24d868a52ea9c6f1e95ce8256b178b2d` and `2f608fb97bf9990ac3fe76707b1054d83e1ebadeff3e23907b960235d89f2419`. Both pass pinned `.venv-cpu/bin/python runtime.py offline`; the exact offline logs each hash to `81fc656524315f8904cb78811b0065768740f407d89893bdc6634e62fe93dd1e`.
- `departure_saved_measure.py` requires source hashes for highway bounds/dedication/access, parking permission and initial parking purpose. It joins original Native trace, `FrameMap` and OpenDRIVE bytes. It reports start frame, surface gap at start and during early departure, and observed traffic deceleration without a safety verdict. `prove_departure_saved_measure.py` passes three 600-frame/20-Hz synthetic positives (clear, closer conflict, parking-exception context) and ten damaged-source negatives under normal and optimized Python. Both logs hash to `54c1404c9c2857ce20d6fa3a56f3ab16967e10345b4ea0403c0331dd644776d0`.
- `.venv-cpu/bin/python worker_check.py --assignment training__C227853__NRS-484B-410__motor_vehicle_driver --complete` passes for the partial checkpoint.

The draft Native context leaves highway dedication, public access, parking permission and purpose null. These remain fail-closed until independently sourced. The approaching vehicle's requested start does not establish that the conflict physically occurred. Numeric gap, time-to-conflict and braking observations are engineering evidence, never statutory safety thresholds.

## Exact remaining CPU work

1. Decompose and implement stopped/standing highway starts, highway entry, and the no-parking exception, while preserving this frozen curb cell where compatible.
2. Complete source-reviewed saved finalization, positive/missing-source compatibility and recorded-only processing, all four video decodes, and participant/pixel audits for each final selected case.
3. Add physical-risk fallback constructions, semantic/Core proposals, independent delivery and controlled-comparison audits; bind final manifests and pass the assignment strict ready gate.

Status remains `partial`; no safety, physical or accepted-membership outcome is claimed.
