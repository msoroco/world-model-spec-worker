# testing__C101303__NRS-484B-127-1__motor_vehicle_driver

Selected branch: Following before a lane change

Prepared as a CPU-tested first-run capability. Exact offline and positive/negative compatibility-recipe checks passed; their SHA-256 receipts are bound in execution-manifest.json.

First GPU capability command:

```sh
python3.11 runtime.py capture --manifest work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/execution-manifest.json --case testing__C101303__NRS-484B-127-1__motor_vehicle_driver__selected_following_before_lane_change --output .runtime-work/attempts/testing__C101303__NRS-484B-127-1__motor_vehicle_driver__selected_following_before_lane_change --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Local review must verify native route, actors, physical signs/signals/markings, all original camera pixels, administrative context and legal interpretation. No CARLA run or physical acceptance is claimed.
