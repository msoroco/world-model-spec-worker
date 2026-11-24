# C412593 NRS 484B.413(2) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `6fa5aeea3db47244eed1630d17d931b2eac506cff6d0f8030bca958ad4cad3d3`. Four prior accepted recording IDs are retained in `case-plan.json`; frozen metadata and authored review settings do not prove the original continuous-signal distance, because original traces and videos are absent.

## Constructed and tested

`turn_signal_probe.py` measures original-frame route arc length for the continuous correct turn signal before a unique source-bound course-change onset. It uses the express 100-foot (30.48 m) business/residential and 300-foot (91.44 m) other-area floors, requires district/weather/route/motion/indicator source bindings, and rejects missing sources or ambiguous onset. The weather value is retained but does not change the statutory floor. No startup transient or time-only proxy is used.

`case-plan.json` now plans ten exact cases and four controlled comparisons: business, residential and other-area short/at/long signaling, plus business weather invariance. Four prior accepted metadata IDs are linked to their authored cases without asserting measured reuse or selecting duplicate captures. Each case states a physical risk.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `054bc2cc5aff6eb6e0dd65f26000135cdfc049d5fbb7be0f32111add13912378`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `d80bf9026271d0d24223dd4d5c6567784d01c9af6503a46fbb8826b32daa160c`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver`: exit 0, `static.log` SHA256 `18b424d656d42a5dc25c6f7237da56abca4f6d76a5c10642694bec0c12a95941`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects truthful partial status.

## Next CPU work

Review the four prior original recordings when available; do not count metadata as measured coverage or duplicate them prematurely. Construct district-sourced route and turn controllers, original indicator/motion capture and exact saved finalizer for every still-needed case. Add offline construction and positive/negative compatibility receipts, semantic proposals, saved-only processing, independent delivery/comparison audits, manifest and queue entries. Recheck full law and exact source sufficiency. Actual signaling, weather visibility and route motion require later CARLA/original recording verification.
