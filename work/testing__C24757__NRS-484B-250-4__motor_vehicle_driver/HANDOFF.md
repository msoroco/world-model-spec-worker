# testing__C24757__NRS-484B-250-4__motor_vehicle_driver

Selected branch: Blind-intersection post-stop interactions under complete signal inoperability.

Prepared as a CPU-tested first-run capability. Exact offline and positive/negative compatibility-recipe checks passed; their SHA-256 receipts are bound in execution-manifest.json.

First GPU capability command:

```sh
python3.11 runtime.py capture --manifest work/testing__C24757__NRS-484B-250-4__motor_vehicle_driver/execution-manifest.json --case testing__C24757__NRS-484B-250-4__motor_vehicle_driver__selected_inoperative_signal_stop_and_yield --output .runtime-work/attempts/testing__C24757__NRS-484B-250-4__motor_vehicle_driver__selected_inoperative_signal_stop_and_yield --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Local review must verify native route, actors, physical signs/signals/markings, all original camera pixels, administrative context and legal interpretation. No CARLA run or physical acceptance is claimed.
