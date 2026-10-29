Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_wide --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-0 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_wide --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-0 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_narrow --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-1 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_none_narrow --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-1 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-1.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_group_and_entrant_combination_wide --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-2

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-2 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-2.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_group_and_entrant_combination_wide --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-2 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-2 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-2.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_group_and_entrant_combination_narrow --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-3

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-3 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-3.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_group_and_entrant_combination_narrow --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-3 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-3 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-3.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_none_wide --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-4

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-4 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-4.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_none_wide --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-4 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-4 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-4.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_none_narrow --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-5

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-5 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-5.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_none_narrow --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-5 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-5 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-5.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_group_and_entrant_combination_wide --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-6

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-6 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-6.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_group_and_entrant_combination_wide --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-6 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-6 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-6.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_group_and_entrant_combination_narrow --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-7

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-7 --receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-7.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/execution-manifest.json --case testing__C160013__NRS-484B-127-3__motor_vehicle_driver__motorcade_group_and_entrant_combination_narrow --attempt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/native002-7 --output .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/processed002-7 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C160013__NRS-484B-127-3__motor_vehicle_driver/owner002-7.json