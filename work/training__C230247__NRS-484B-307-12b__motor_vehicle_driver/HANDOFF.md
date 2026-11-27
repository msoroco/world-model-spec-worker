# C230247 NRS 484B.307(12)(b) red-X lane preparation

Status: CPU delivery preparation passed the exact assignment strict gate. The frozen highway road/travel/lane-signal cell has no accepted recording IDs. The exact rule prohibits entering or driving in a lane when a red X faces the driver over that individual lane. The two cases preserve the overhead signal, road, actor, duration and cameras: probe_1 travels in adjacent lane -2; probe_2 requests a lane -2 to lane -1 crossing under the red X over lane -1. No grace period, clearance allowance, numeric legal cutoff or compliance verdict is asserted.

## Native construction and capture

- Both `construction.json` files and source-shaped diagnostic recipes bind the original map signal ID 100 to lane -1. `native/signal_source.py` rejects a generic traffic light or a lane-control actor without the exact `red_x` display role and map signal binding.
- `runner.py`, `draft_runner.py`, `capture.py`, `finalize.py`, `road.xodr`, `config.json` and `tests/test_native.py` materialize each case's execution bundle. The plan requests 600 frames at 20 Hz for 30 seconds with four original camera streams. Probe_2 requests lateral motion only during frames 200–299.
- `lane_red_x_meter.py` measures signal facing and governed-lane body overlap from saved map, signal, trace, frame and evidence sources. It provides a source-bound statistic without a legal verdict. Positive and negative CPU fixtures reject missing sources.

## Completed CPU proofs

- Exact offline runs and public compatibility checks passed for both cases; their v4 logs and receipts are in this directory.
- Saved-only processing passed four positive and missing-source tests. Physical outcome proof passed complete, incomplete and missing-evidence paths for each case.
- Canonical semantic delivery validated six stages and both selected cases. Independent delivery and comparison structure audits passed positive and negative fixtures.
- Native unit tests passed two tests. The execution manifest binds the runtime, construction hashes, camera and duration plan, post-capture commands, and no-alternate-source risk assessment.
- `.venv-cpu/bin/python worker_check.py --assignment training__C230247__NRS-484B-307-12b__motor_vehicle_driver --complete --require-delivery-ready` exited 0 with `static_checks_passed: true` on 2026-11-27.

GPU capture, original red-X pixels, device authority, physical completion and official provenance remain for independent delivery review. No accepted recording or legal compliance determination is claimed.
