# Update 012 current CPU handoff

The exact primary, fallback1, saved-processing, comparison, and synthetic integration CPU proofs are source-hashed in `work/_shared/v6-proof-index.json`. The frozen v6 checker rejects the required neutral baseline at `preparation.py:228`; this package remains partial. The commands below are planned and have not executed a Native recording.

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation requires the case-specific `fallback_trigger_command` in `work/_shared/gpu-queue.json` to report `triggered: true`. The queue supplies saved processing, independent audit, acceptance, and comparison commands.

## Earlier handoff notes
# Delivery preparation handoff

Assignment: `testing__C158190__NRS-484B-257-2__motor_vehicle_driver`
Selected exact cases: 13
Controlled comparisons: 9

## First local GPU command

```sh
python3.11 work/_shared/runtime-v3.py runtime.py capture --manifest work/testing__C158190__NRS-484B-257-2__motor_vehicle_driver/execution-manifest.json --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C158190__NRS-484B-257-2__motor_vehicle_driver/native002-0
```

## CPU evidence

Every selected construction passed an exact offline check and a v3 compatibility recipe against the case-specific v3 retained-speed fixture. Every exact case passed saved-only processing and positive/negative independent audit fixtures. The manifest binds source hashes, logs, and commands; the semantic-index binds all canonical stage proposals. Diagnostic fixtures establish software behavior only.

## Remaining local checks

Run the ordered GPU queue with actual Native Python and CARLA, review original four-view pixels, complete participant histories and physical motion, then run the independent delivery audit and comparison audits. Legal judgments and canonical acceptance remain unresolved.
