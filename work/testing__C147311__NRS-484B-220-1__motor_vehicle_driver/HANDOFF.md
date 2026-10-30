# Update 013 CPU delivery handoff

The exact primary, fallback1, saved-processing, comparison, and synthetic integration CPU proofs are indexed in `work/_shared/v7-proof-index.json`. This package is delivery prepared. Canonical GPU capture, saved-recording audits, acceptance, and comparison audits remain pending. No physical acceptance or accepted recording is claimed.

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__designated --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__designated --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Select fallback1 only when its case-specific measured trigger in `work/_shared/gpu-queue.json` fires. The queue holds the ordered saved processing, independent audit, acceptance, and comparison commands.
