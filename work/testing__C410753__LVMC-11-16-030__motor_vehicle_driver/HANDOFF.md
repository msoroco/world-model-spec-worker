# C410753 / LVMC 11.16.030 railway grade crossing

Status: **partial**. No accepted original recording is in the frozen evidence inventory. The selected branch is traversal of a railway grade crossing with the sight condition and neither exception. The exact text also requires independent coverage of the flagman and installed, clearly visible nonwarning crossing signal exceptions. No legal visibility or speed verdict is produced by this package.

## Current case and comparison construction

`build_case_plan.py` expands `case-plan.json` into seven selected targets: `obscured_14mph`, `obscured_15mph`, `obscured_16mph`, `clear_view_16mph`, `flagman_16mph`, `signal_nonwarning_16mph`, and `signal_warning_16mph` (each prefixed with this assignment ID). The first three probe below, at and above the statutory 15 mph prima facie boundary; the latter four separate sight and the two exceptions. Three comparisons hold the reviewed site and vehicle fixed across speed, sight, and exception states. These are engineering targets, never observed outcomes.

`rail_sight_measurement.py` validates a source-hashed municipal railway grade-crossing review against live OpenDRIVE, enforces 100 feet of approach and 400 feet along the rail in both directions, checks contiguous original 20 Hz frame joins, separately hashes original frame and sight ray sources, measures body traversal speed, and leaves legal judgment null. `rail_route_reader.py` projects original ego position and all eight body vertices onto a reviewed source-hashed route to determine crossing occupancy. `rail_ray_reader.py` casts original Native rays from an ego reference eye to reviewed crossing geometry and samples of each 400-foot railway direction, retaining hit traces. `rail_exception_reader.py` requires reviewed duty and signal authority plus source-hashed original-frame readbacks rather than treating a spawned device as an established exception. `rail_construction.py` validates a separately reviewed occluder source, creates a Native prop only for obscured targets and checks spawn position and lifecycle. `rail_native_capture.py` is a lazy 900-frame operator capture that takes real route, ray, exception and four-camera readers, records original PNG bytes and source hashes, and brakes the ego on exit. The `frame_count` override is only for CPU tests; the production call requires 900 frames for its receipt.

The eleven focused CPU tests in `tests/test_rail_sight_measurement.py` exercise the measurement, tampered original ray and frame sources, relabeled body/exception state, signal exception separation, reviewed body occupancy, bidirectional railway ray hits, original exception readbacks, reviewed occluder spawning and a four-camera capture with fake world readers. Run:

`SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c410753-tests/output" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C410753__LVMC-11-16-030__motor_vehicle_driver/tests -p 'test_rail_sight_measurement.py' -v`

The exact static partial gate passes:

`SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c410753-gate/output" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C410753__LVMC-11-16-030__motor_vehicle_driver --complete`

## Next CPU construction and proof

Wire the reviewed occluder, 45-second Native controller, four cameras, finalization and saved-only processing into selected case commands. Then materialize each selected case and any risk-justified fallback, semantic proposals, positive and missing-source compatibility receipts, physical/lifecycle probes and independent delivery/comparison audits. Run the exact strict assignment gate only after those proofs are bound. Actual CARLA motion, visibility and camera quality remain later physical checks.
