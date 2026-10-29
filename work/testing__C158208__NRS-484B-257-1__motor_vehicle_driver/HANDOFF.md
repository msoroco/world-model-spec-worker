# Exact CPU capability handoff

Assignment: `testing__C158208__NRS-484B-257-1__motor_vehicle_driver`

Selected branch: Yield sign; neither stop line nor crosswalk; nearest-view location.

Offline log SHA-256: `5c3e8621ef7601a549a39e775954d45668fdae6204aae80c333cbf7cb22ff5ef`

Compatibility receipt SHA-256: `51e79e5e4bdcdedd1c280e39c00ddba107f17d5dffc535291aac23846bb5dd0a`

First GPU capability command:

```sh
python3.11 runtime.py capture --manifest work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json --case testing__C158208__NRS-484B-257-1__motor_vehicle_driver__selected --output .runtime-work/attempt-testing__C158208__NRS-484B-257-1__motor_vehicle_driver --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Review native topology, actor class/width, sign and crosswalk inventory, original ray samples and pixels, controller outcome and legal judgments. The diagnostic fixture proves software compatibility only.
