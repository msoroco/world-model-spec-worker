# Delivery preparation handoff

Assignment: `testing__C157964__NRS-484B-257-1__motor_vehicle_driver`
Selected exact cases: 2
Controlled comparisons: 1

## First local GPU command

```sh
python3.11 work/_shared/runtime-v3.py runtime.py capture --manifest work/testing__C157964__NRS-484B-257-1__motor_vehicle_driver/execution-manifest.json --case testing__C157964__NRS-484B-257-1__motor_vehicle_driver__active_control --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C157964__NRS-484B-257-1__motor_vehicle_driver/native002-0
```

## CPU evidence

Every selected construction passed an exact offline check and a v3 compatibility recipe against the case-specific v3 retained-speed fixture. Every exact case passed saved-only processing and positive/negative independent audit fixtures. The manifest binds source hashes, logs, and commands; the semantic-index binds all canonical stage proposals. Diagnostic fixtures establish software behavior only.

## Remaining local checks

Run the ordered GPU queue with actual Native Python and CARLA, review original four-view pixels, complete participant histories and physical motion, then run the independent delivery audit and comparison audits. Legal judgments and canonical acceptance remain unresolved.
