# C136559 CPU handoff — NRS 484B.600(1)(c)

Status: **partial**. The selected branch is a posted-speed obligation on a narrow road (`narrow_road/travel/speed_limit_sign`). The exact statute requires a speed greater than the rate posted by a public authority for the particular highway portion traversed. The frozen `evidence.json` has zero accepted recordings, so there is no reuse.

`case-plan.json` names fresh below, at, above and outside-governed-zone cases and fixed-condition comparisons. `sign_construction.py` selects a Native speed-limit sign by actor type, posted value and physical trigger. `speed_controller.py` applies bounded Native throttle/brake with measured speed and route-end braking. `posted_speed_measurements.py` requires original-frame subject velocity, frame joins, sourced sign/authority/road boundaries and a signed road-coordinate interval; it compares only motion inside that interval. It leaves public-authority status and legal conclusion unresolved. Four CPU tests pass in `cpu-tests.log`, including 24.99/25/25.01 mph diagnostic probes, outside-zone exclusion, missing authority, stale frame, sign trigger and actual `apply_control` calls. Those speeds are test fixture values, not a frozen statutory rate.

Next CPU work: find a source-backed narrow highway and posted limit with public-authority governance, implement exact scene and vehicle route, capture all four named raw source-camera streams and map/sign/motion sources, then write the saved finalizer and measurement contract. Implement three distinct physical-risk fallback constructions per selected case, canonical semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Rerun assignment-scoped `worker_check.py --complete --require-delivery-ready` only when those proofs and required package files exist. The physical sign, highway status, governed portion, vehicle motion and visibility require later CARLA/source review; the listed implementation and CPU proofs remain worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The full strict gate next reports missing result `testing__C149752__NRS-484B-127-2__heavy_vehicle_driver` in `strict-gate.log`; that assignment was subsequently checkpointed separately.

Latest CPU progress: `finalizer.py` reads saved original motion/frame map/sign context, all four source camera paths, trace and capture evidence; it writes the measured in-zone peak and posted limit to a Native result via pinned `write_result` and `physical_result`. It makes no public-authority or legal conclusion. `tests/test_finalizer.py` verifies the positive path and that removing `sign_context.json` fails without producing a result. Six tests now pass. Measurement contract, exact runner, manifest and proof receipts remain unfinished.

`case-plan.json` now binds the exact posted-rate and governed-portion comparisons, the zero-recording evidence gap, all six supplied observation terms, and the selected statutory requirement to exact case IDs. These mappings are plans; no road authority, sign face, highway portion or physical realization has been established by the CPU fixture.

`measurement-contract.json` binds disposition 0 to `measure_peak_in_signed_zone` and original motion, frame-map and sign-context sources. The positive fixture validates and verifies the report against the pinned measurement-contract checker; removal of sign context remains the negative proof. This is component-level, not `runtime.py compatibility` or saved-processing readiness.
