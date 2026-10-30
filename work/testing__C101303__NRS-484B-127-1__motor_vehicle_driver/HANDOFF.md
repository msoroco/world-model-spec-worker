# Delivery preparation

Selected cases are CPU prepared for canonical demo-test and full-test delivery. No Native run, pixel visibility, physical completion, legal judgment, or acceptance is claimed.

First Native command: `python3.11 work/_shared/runtime-v3.py runtime.py capture --manifest work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/execution-manifest.json --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__base --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/native002-0`

After local resource owner release, run each manifest `post_capture.command`, promote saved derived outputs with `work/_shared/promote_saved_delivery.py`, then run each `delivery_acceptance.command` against the canonical recording. Run the ordered comparison audits in `work/_shared/gpu-queue.json`.
