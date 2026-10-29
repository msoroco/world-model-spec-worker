Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__precedence --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-0 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__precedence --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-0 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__advance --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-1 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__advance --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-1 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-1.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__other_later --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-2

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-2 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-2.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__other_later --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-2 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-2 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-2.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_straight --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-3

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-3 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-3.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_straight --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-3 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-3 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-3.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_intends_left --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-4

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-4 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-4.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_intends_left --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-4 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-4 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-4.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_makes_left --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-5

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-5 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-5.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__opposite_makes_left --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-5 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-5 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-5.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__wide_same_crossing --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-6

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-6 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-6.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__wide_same_crossing --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-6 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-6 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-6.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__wide_separate_crossing --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-7

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-7 --receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-7.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125714__NRS-484B-250-2__motor_vehicle_driver__wide_separate_crossing --attempt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/native002-7 --output .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/processed002-7 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/owner002-7.json