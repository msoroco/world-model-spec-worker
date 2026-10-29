Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_160 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-0 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_160 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-0 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_140 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-1 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_truck_140 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-1 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-1.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_combination_160 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-2

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-2 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-2.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_combination_160 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-2 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-2 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-2.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_combination_140 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-3

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-3 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-3.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__truck_combination_140 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-3 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-3 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-3.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_truck_160 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-4

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-4 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-4.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_truck_160 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-4 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-4 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-4.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_truck_140 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-5

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-5 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-5.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_truck_140 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-5 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-5 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-5.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_combination_160 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-6

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-6 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-6.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_combination_160 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-6 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-6 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-6.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_combination_140 --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-7

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-7 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-7.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__combination_combination_140 --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-7 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-7 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-7.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__subject_width_probe --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-8

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-8 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-8.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__subject_width_probe --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-8 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-8 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-8.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__lead_width_probe --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-9

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-9 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-9.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__lead_width_probe --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-9 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-9 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-9.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__constrained_conditions --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-10

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-10 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-10.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__constrained_conditions --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-10 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-10 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-10.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__entrant_late --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-11

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-11 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-11.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__entrant_late --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-11 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-11 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-11.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__two_available_lanes --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-12

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-12 --receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-12.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/execution-manifest.json --case testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__two_available_lanes --attempt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/native002-12 --output .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/processed002-12 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C149237__NRS-484B-127-2__heavy_vehicle_driver/owner002-12.json