# testing__C136559__NRS-484B-600-1c__motor_vehicle_driver

Selected branch: Posted-speed obligation on a narrow road.

Prepared as a CPU-tested first-run capability. Exact offline and positive/negative compatibility-recipe checks passed; their SHA-256 receipts are bound in execution-manifest.json.

First GPU capability command:

```sh
python3.11 runtime.py capture --manifest work/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver/execution-manifest.json --case testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__selected_narrow_posted_speed --output .runtime-work/attempts/testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__selected_narrow_posted_speed --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Local review must verify native route, actors, physical signs/signals/markings, all original camera pixels, administrative context and legal interpretation. No CARLA run or physical acceptance is claimed.
