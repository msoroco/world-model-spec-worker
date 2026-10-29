Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.

Saved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__precedence --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-0

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-0 --receipt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/owner002-0.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__precedence --attempt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-0 --output .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/processed002-0 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/owner002-0.json

python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__advance --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-1

After actual operator resource release:

python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-1 --receipt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/owner002-1.json --acknowledge-owner-released

python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125697__NRS-484B-250-2__motor_vehicle_driver__advance --attempt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/native002-1 --output .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/processed002-1 --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/owner002-1.json