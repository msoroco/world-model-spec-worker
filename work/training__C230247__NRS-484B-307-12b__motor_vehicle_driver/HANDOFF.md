# C230247 NRS 484B.307(12)(b) red-X lane preparation

Status: partial. The frozen highway road/travel/lane-signal cell has no accepted recording IDs. Exact text: a driver facing a red X over an individual lane must not enter or drive in that lane. The two exact cases hold the original overhead signal, road, actor, duration and cameras fixed; probe_1 travels in adjacent lane -2, and probe_2 requests a lane -2 to lane -1 crossing while the red X remains over lane -1. No grace period, clearance allowance, numeric legal cutoff or compliance verdict is asserted.

## Exact constructions

- `__probe_1`: `construction.json`, `config.json`, source-shaped `diagnostic-probe_1-recipe.json`.
- `__probe_2`: `cases/probe_2/construction.json`, `cases/probe_2/config.json`, source-shaped `diagnostic-probe_2-recipe.json`.
- `native/road.xodr` defines two 3.5 m driving lanes and original signal ID 100 valid only for lane -1, mounted at x=60 m over its center. `native/signal_source.py` rejects a generic traffic light or a lane-control actor without an exact `red_x` display role and original map signal binding.
- `native/draft_runner.py` requests 2.5 m/s travel for both cases and a 0.7 m/s lateral crossing only during frames 200–299 of probe_2. `native/capture.py` attempts 600 original 20 Hz frames, four original camera streams, map readback, actor body vertices, lane projection, trace, video-frame map and Native graph sources. It restores the exclusively owned world. Physical behavior, red-X pixels and official provenance await independent local review.
- `native/lane_red_x_meter.py` measures red-X-facing frames and governed-lane body overlap without a legal verdict. `native/finalize.py` joins original map, signal, trace, video-frame and evidence sources, writes result and an analysis report, and rejects missing sources.

## CPU proofs completed

- `.venv-cpu/bin/python runtime.py verify --runtime runtime`: exit 0.
- `.venv-cpu/bin/python runtime.py preflight`: exit 0 with pinned CPU tools, ffmpeg and Lean available.
- `.venv-cpu/bin/python runtime.py offline --manifest work/training__C230247__NRS-484B-307-12b__motor_vehicle_driver/draft-manifest.json --case training__C230247__NRS-484B-307-12b__motor_vehicle_driver__probe_1 --output .runtime-work/c230247-12b-probe_1-offline`: exit 0; sanitized proof `probe_1-offline.log`.
- Same command for `__probe_2` and `.runtime-work/c230247-12b-probe_2-offline`: exit 0; `probe_2-offline.log`.
- `.venv-cpu/bin/python work/training__C230247__NRS-484B-307-12b__motor_vehicle_driver/native/prove_meter.py`: exit 0; `native/meter-proof.log`. Outside case has zero lane overlap; entry fixture first overlaps at frame 228 and has 327 wholly inside frames. Five bad-source variants are rejected. This is source-shaped CPU evidence only.

## Remaining CPU work

Finish both public compatibility receipts, saved-only positive/negative processing, physical completion and independent delivery/comparison audits, canonical semantic proposals, exact execution manifest, fallback risk assessment and scoped strict gate. Keep result partial until `worker_check.py --assignment training__C230247__NRS-484B-307-12b__motor_vehicle_driver --complete --require-delivery-ready` passes. Temporary fixtures belong under `.runtime-work`.
