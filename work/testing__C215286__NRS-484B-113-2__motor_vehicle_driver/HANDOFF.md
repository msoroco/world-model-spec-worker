Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__marked_crosswalk --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-0 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__marked_crosswalk --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-0 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_marked --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-1 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_marked --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-1 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-1.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__intersection --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-2

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-2 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-2.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__intersection --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-2 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-2 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-2.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_intersection --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-3

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-3 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-3.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_intersection --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-3 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-3 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-3.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__sidewalk_crosswalk --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-4

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-4 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-4.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__sidewalk_crosswalk --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-4 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-4 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-4.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_sidewalk --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-5

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-5 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-5.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_sidewalk --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-5 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-5 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-5.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__street_corner --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-6

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-6 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-6.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__street_corner --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-6 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-6 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-6.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_corner --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-7

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-7 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-7.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__clear_corner --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-7 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-7 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-7.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__forward_overlap --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-8

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-8 --receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-8.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__forward_overlap --attempt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/native002-8 --output .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/processed002-8 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/owner002-8.json