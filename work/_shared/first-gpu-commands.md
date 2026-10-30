# First canonical delivery commands

Preparation returns the run and exact job ID. Execution uses those values with the operator-owned Native Python and server. These are planned commands, not executed GPU work.

## testing__C101303__NRS-484B-127-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C101303__NRS-484B-127-1__motor_vehicle_driver --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__base --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C101303__NRS-484B-127-1__motor_vehicle_driver --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__base --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C101303__NRS-484B-127-1__motor_vehicle_driver --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__base --candidate fallback1`

## testing__C10301__NRS-484B-600-1e__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --case testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --case testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C10301__NRS-484B-600-1e__motor_vehicle_driver --case testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below --candidate fallback1`

## testing__C109705__NRS-484B-400-2a__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__near_centerline --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__near_centerline --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__near_centerline --candidate fallback1`

## testing__C109705__NRS-484B-400-2b__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --case testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline --candidate fallback1`

## testing__C109749__NRS-484B-253__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --case testing__C109749__NRS-484B-253__motor_vehicle_driver__inside_yield --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --case testing__C109749__NRS-484B-253__motor_vehicle_driver__inside_yield --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --case testing__C109749__NRS-484B-253__motor_vehicle_driver__inside_yield --candidate fallback1`

## testing__C125697__NRS-484B-250-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-1__motor_vehicle_driver --case testing__C125697__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-1__motor_vehicle_driver --case testing__C125697__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-1__motor_vehicle_driver --case testing__C125697__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125697__NRS-484B-250-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125697__NRS-484B-250-2__motor_vehicle_driver --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125714__NRS-484B-250-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-1__motor_vehicle_driver --case testing__C125714__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-1__motor_vehicle_driver --case testing__C125714__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-1__motor_vehicle_driver --case testing__C125714__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125714__NRS-484B-250-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125714__NRS-484B-250-2__motor_vehicle_driver --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125745__NRS-484B-250-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-1__motor_vehicle_driver --case testing__C125745__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125745__NRS-484B-250-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --case testing__C125745__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --case testing__C125745__NRS-484B-250-2__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --case testing__C125745__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125751__NRS-484B-250-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-1__motor_vehicle_driver --case testing__C125751__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-1__motor_vehicle_driver --case testing__C125751__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-1__motor_vehicle_driver --case testing__C125751__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125751__NRS-484B-250-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-2__motor_vehicle_driver --case testing__C125751__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-2__motor_vehicle_driver --case testing__C125751__NRS-484B-250-2__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125751__NRS-484B-250-2__motor_vehicle_driver --case testing__C125751__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125763__NRS-484B-250-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-1__motor_vehicle_driver --case testing__C125763__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-1__motor_vehicle_driver --case testing__C125763__NRS-484B-250-1__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-1__motor_vehicle_driver --case testing__C125763__NRS-484B-250-1__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C125763__NRS-484B-250-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__precedence --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__precedence --candidate fallback1`

## testing__C126120__NRS-484B-227-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C126120__NRS-484B-227-1__motor_vehicle_driver --case testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C126120__NRS-484B-227-1__motor_vehicle_driver --case testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C126120__NRS-484B-227-1__motor_vehicle_driver --case testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening --candidate fallback1`

## testing__C129731__NRS-484B-407__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C129731__NRS-484B-407__motor_vehicle_driver --case testing__C129731__NRS-484B-407__motor_vehicle_driver__curve_clear --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C129731__NRS-484B-407__motor_vehicle_driver --case testing__C129731__NRS-484B-407__motor_vehicle_driver__curve_clear --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C129731__NRS-484B-407__motor_vehicle_driver --case testing__C129731__NRS-484B-407__motor_vehicle_driver__curve_clear --candidate fallback1`

## testing__C136559__NRS-484B-600-1c__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --case testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__below --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --case testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__below --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C136559__NRS-484B-600-1c__motor_vehicle_driver --case testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__below --candidate fallback1`

## testing__C144550__NRS-484B-223-1b__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --case testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__signal_and_open_gap --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --case testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__signal_and_open_gap --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C144550__NRS-484B-223-1b__motor_vehicle_driver --case testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__signal_and_open_gap --candidate fallback1`

## testing__C147311__NRS-484B-220-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__designated --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__designated --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver --case testing__C147311__NRS-484B-220-1__motor_vehicle_driver__designated --candidate fallback1`

## testing__C149237__NRS-484B-127-2__heavy_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_160 --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_160 --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149237__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_160 --candidate fallback1`

## testing__C149752__NRS-484B-127-2__heavy_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149752__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149752__NRS-484B-127-2__heavy_vehicle_driver__follow_reference --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149752__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149752__NRS-484B-127-2__heavy_vehicle_driver__follow_reference --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C149752__NRS-484B-127-2__heavy_vehicle_driver --case testing__C149752__NRS-484B-127-2__heavy_vehicle_driver__follow_reference --candidate fallback1`

## testing__C157964__NRS-484B-257-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-1__motor_vehicle_driver --case testing__C157964__NRS-484B-257-1__motor_vehicle_driver__active_control --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-1__motor_vehicle_driver --case testing__C157964__NRS-484B-257-1__motor_vehicle_driver__active_control --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-1__motor_vehicle_driver --case testing__C157964__NRS-484B-257-1__motor_vehicle_driver__active_control --candidate fallback1`

## testing__C157964__NRS-484B-257-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --case testing__C157964__NRS-484B-257-2__motor_vehicle_driver__active_control --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --case testing__C157964__NRS-484B-257-2__motor_vehicle_driver__active_control --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --case testing__C157964__NRS-484B-257-2__motor_vehicle_driver__active_control --candidate fallback1`

## testing__C158190__NRS-484B-257-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --case testing__C158190__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --case testing__C158190__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --case testing__C158190__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --candidate fallback1`

## testing__C158190__NRS-484B-257-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --case testing__C158190__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --candidate fallback1`

## testing__C158196__NRS-484B-257-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --case testing__C158196__NRS-484B-257-1__motor_vehicle_driver__active_control --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --case testing__C158196__NRS-484B-257-1__motor_vehicle_driver__active_control --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --case testing__C158196__NRS-484B-257-1__motor_vehicle_driver__active_control --candidate fallback1`

## testing__C158196__NRS-484B-257-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --case testing__C158196__NRS-484B-257-2__motor_vehicle_driver__active_control --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --case testing__C158196__NRS-484B-257-2__motor_vehicle_driver__active_control --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --case testing__C158196__NRS-484B-257-2__motor_vehicle_driver__active_control --candidate fallback1`

## testing__C158196__NRS-484B-307-6a__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --case testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__stops_red --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --case testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__stops_red --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --case testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__stops_red --candidate fallback1`

## testing__C158208__NRS-484B-257-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response --candidate fallback1`

## testing__C158208__NRS-484B-257-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --case testing__C158208__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --case testing__C158208__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --case testing__C158208__NRS-484B-257-2__motor_vehicle_driver__nearest_view_response --candidate fallback1`

## testing__C160013__NRS-484B-127-3__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_wide --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_wide --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C160013__NRS-484B-127-3__motor_vehicle_driver --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_wide --candidate fallback1`

## testing__C177008__NRS-484B-413-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --case testing__C177008__NRS-484B-413-2__motor_vehicle_driver__business_continuous --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --case testing__C177008__NRS-484B-413-2__motor_vehicle_driver__business_continuous --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --case testing__C177008__NRS-484B-413-2__motor_vehicle_driver__business_continuous --candidate fallback1`

## testing__C178244__NRS-484B-413-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --case testing__C178244__NRS-484B-413-2__motor_vehicle_driver__business_continuous --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --case testing__C178244__NRS-484B-413-2__motor_vehicle_driver__business_continuous --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --case testing__C178244__NRS-484B-413-2__motor_vehicle_driver__business_continuous --candidate fallback1`

## testing__C179789__NRS-484B-600-1a__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C179789__NRS-484B-600-1a__motor_vehicle_driver --case testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__reference --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C179789__NRS-484B-600-1a__motor_vehicle_driver --case testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__reference --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C179789__NRS-484B-600-1a__motor_vehicle_driver --case testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__reference --candidate fallback1`

## testing__C215286__NRS-484B-113-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__marked_crosswalk --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__marked_crosswalk --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__marked_crosswalk --candidate fallback1`

## testing__C24757__NRS-484B-250-4__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24757__NRS-484B-250-4__motor_vehicle_driver --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24757__NRS-484B-250-4__motor_vehicle_driver --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24757__NRS-484B-250-4__motor_vehicle_driver --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__line_stop --candidate fallback1`

## testing__C24811__NRS-484B-250-4__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --case testing__C24811__NRS-484B-250-4__motor_vehicle_driver__dark_heads --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --case testing__C24811__NRS-484B-250-4__motor_vehicle_driver__dark_heads --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --case testing__C24811__NRS-484B-250-4__motor_vehicle_driver__dark_heads --candidate fallback1`

## testing__C331230__NRS-484A-450-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C331230__NRS-484A-450-2__motor_vehicle_driver --case testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_halt --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C331230__NRS-484A-450-2__motor_vehicle_driver --case testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_halt --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C331230__NRS-484A-450-2__motor_vehicle_driver --case testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_halt --candidate fallback1`

## testing__C376646__NRS-484B-250-4__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --case testing__C376646__NRS-484B-250-4__motor_vehicle_driver__no_installed_signal_stop --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --case testing__C376646__NRS-484B-250-4__motor_vehicle_driver__no_installed_signal_stop --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --case testing__C376646__NRS-484B-250-4__motor_vehicle_driver__no_installed_signal_stop --candidate fallback1`

## testing__C378304__NRS-484B-413-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C378304__NRS-484B-413-2__motor_vehicle_driver --case testing__C378304__NRS-484B-413-2__motor_vehicle_driver__continuous100 --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C378304__NRS-484B-413-2__motor_vehicle_driver --case testing__C378304__NRS-484B-413-2__motor_vehicle_driver__continuous100 --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C378304__NRS-484B-413-2__motor_vehicle_driver --case testing__C378304__NRS-484B-413-2__motor_vehicle_driver__continuous100 --candidate fallback1`

## testing__C412593__NRS-484B-413-2__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous --candidate fallback1`

## testing__C80909__NRS-484B-227-1__motor_vehicle_driver

```sh
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C80909__NRS-484B-227-1__motor_vehicle_driver --case testing__C80909__NRS-484B-227-1__motor_vehicle_driver__opening_aligned --candidate primary
python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" execute-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C80909__NRS-484B-227-1__motor_vehicle_driver --case testing__C80909__NRS-484B-227-1__motor_vehicle_driver__opening_aligned --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Fallback preparation if the measured trigger fires: `python3.11 -m scenario_pipeline.worker_exchange --root "$PIPELINE_ROOT" prepare-delivery --repo "$LOCAL_CHECKOUT" --batch demo-test-full-branches-v7 --db "$DB" --assignment testing__C80909__NRS-484B-227-1__motor_vehicle_driver --case testing__C80909__NRS-484B-227-1__motor_vehicle_driver__opening_aligned --candidate fallback1`
