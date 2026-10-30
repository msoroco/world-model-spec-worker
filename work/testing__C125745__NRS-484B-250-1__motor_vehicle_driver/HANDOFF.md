# Update 012 current CPU handoff

The exact primary, fallback1, saved-processing, comparison, and synthetic integration CPU proofs are source-hashed in `work/_shared/v6-proof-index.json`. The frozen v6 checker rejects the required neutral baseline at `preparation.py:228`; this package remains partial. The commands below are planned and have not executed a Native recording.

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation requires the case-specific `fallback_trigger_command` in `work/_shared/gpu-queue.json` to report `triggered: true`. The queue supplies saved processing, independent audit, acceptance, and comparison commands.

## Earlier handoff notes
# Delivery preparation handoff

Assignment: `testing__C125745__NRS-484B-250-1__motor_vehicle_driver`. Exact selected cases: 2. CPU diagnostic evidence does not establish Native or legal acceptance.

Run cases in `work/_shared/gpu-queue.json` order. The first GPU command is:

```sh
python3.11 work/_shared/runtime-v3.py runtime.py capture --manifest work/testing__C125745__NRS-484B-250-1__motor_vehicle_driver/execution-manifest.json --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125745__NRS-484B-250-1__motor_vehicle_driver/native-delivery-0
```

For each case, the manifest records the exact owner-release, saved-only processing, and independent delivery-audit commands. Release local resources before owner attestation. Promote the source-verified saved result, composed video, four-view receipt and Core trace into canonical evidence before audit. The local operator supplies source-hashed original-frame pixel annotations.

Physical checks still required: CPU fixtures demonstrate software compatibility only. Native motion, pixels, district/public-authority facts and legal judgments remain unverified..
