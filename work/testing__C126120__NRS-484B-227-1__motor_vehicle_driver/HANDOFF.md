# testing__C126120__NRS-484B-227-1__motor_vehicle_driver

Selected branch: U-turn through a median opening, including a multiple-movement variant.

Prepared CPU capability only. Offline and positive/negative compatibility-recipe gates passed; receipts and SHA-256 are bound in execution-manifest.json.

First GPU capability command:

```sh
python3.11 runtime.py capture --manifest work/testing__C126120__NRS-484B-227-1__motor_vehicle_driver/execution-manifest.json --case testing__C126120__NRS-484B-227-1__motor_vehicle_driver__selected_median_opening_uturn --output .runtime-work/attempts/testing__C126120__NRS-484B-227-1__motor_vehicle_driver__selected_median_opening_uturn --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

The operator must verify native route, construction, source acquisition, camera pixels and legal interpretation. No CARLA or physical acceptance was claimed.
