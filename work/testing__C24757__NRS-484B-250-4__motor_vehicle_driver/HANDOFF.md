# Update 012 current CPU handoff

The exact primary, fallback1, saved-processing, comparison, and synthetic integration CPU proofs are source-hashed in `work/_shared/v6-proof-index.json`. The frozen v6 checker rejects the required neutral baseline at `preparation.py:228`; this package remains partial. The commands below are planned and have not executed a Native recording.

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24757__NRS-484B-250-4__motor_vehicle_driver --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24757__NRS-484B-250-4__motor_vehicle_driver --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation requires the case-specific `fallback_trigger_command` in `work/_shared/gpu-queue.json` to report `triggered: true`. The queue supplies saved processing, independent audit, acceptance, and comparison commands.

## Earlier handoff notes
# Delivery preparation

Selected cases are CPU prepared for canonical demo-test and full-test delivery. No Native run, pixel visibility, physical completion, legal judgment, or acceptance is claimed.

First Native command: `python3.11 work/_shared/runtime-v3.py runtime.py capture --manifest work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver/execution-manifest.json --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver/native002-0`

After local resource owner release, run each manifest `post_capture.command`, promote saved derived outputs with `work/_shared/promote_saved_delivery.py`, then run each `delivery_acceptance.command` against the canonical recording. Run the ordered comparison audits in `work/_shared/gpu-queue.json`.
