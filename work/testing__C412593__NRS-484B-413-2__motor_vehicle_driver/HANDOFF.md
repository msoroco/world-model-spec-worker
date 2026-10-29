Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-0 --receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-0 --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_short --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-1 --receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_short --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-1 --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-1.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__other_area_continuous --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-2

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-2 --receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-2.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__other_area_continuous --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-2 --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/processed002-2 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-2.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__other_area_short --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-3

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-3 --receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-3.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/execution-manifest.json --case testing__C412593__NRS-484B-413-2__motor_vehicle_driver__other_area_short --attempt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/native002-3 --output .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/processed002-3 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/owner002-3.json