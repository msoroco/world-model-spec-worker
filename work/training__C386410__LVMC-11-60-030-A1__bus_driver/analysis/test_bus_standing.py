"""CPU-only Native-shaped diagnostic and missing-source rejection probes."""
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bus_standing import measure


def fixture():
    frames = [{
        "frame_id": i, "sim_time_s": i / 20,
        "camera_frames": {name: i for name in ("overview", "approach", "reference_corner", "driver_reference")},
        "bus_speed_mps": 0.0 if 100 <= i < 200 else 5.0,
        "parking_brake_applied": 120 <= i < 200,
        "driver_present": i < 150 or i >= 180,
        "occupied_zone_id": "terminus-1",
    } for i in range(600)]
    context = {"vehicle_class": "route_bus_non_tour", "route_id": "R-1", "street_id": "S-1",
               "zone": {"kind": "route_destination", "id": "terminus-1", "route_id": "R-1",
                        "designation_source": {"path": "authority/route-R-1.json", "sha256": "a" * 64}}}
    return frames, context


frames, context = fixture()
result = measure(frames, context, source_kind="synthetic_native_sample")
assert result["stationary_frames"] == 100
assert result["stationary_brake_applied_frames"] == 80
assert result["stationary_driver_absent_frames"] == 30
assert result["standing_or_parking_judgment"] == "unresolved"
print("positive", json.dumps(result, sort_keys=True))

for name, mutate, expected in [
    ("camera", lambda f, c: f[130]["camera_frames"].pop("driver_reference"), "four source-camera"),
    ("brake", lambda f, c: f[130].pop("parking_brake_applied"), "brake or driver-presence"),
    ("driver", lambda f, c: f[130].pop("driver_present"), "brake or driver-presence"),
    ("designation", lambda f, c: c["zone"].pop("designation_source"), "designation reference"),
    ("route", lambda f, c: c["zone"].update(route_id="R-2"), "assigned route"),
    ("location", lambda f, c: f[130].pop("occupied_zone_id"), "location readback"),
    ("duration", lambda f, c: f.pop(), "shorter than 30 seconds"),
]:
    f, c = copy.deepcopy(frames), copy.deepcopy(context)
    mutate(f, c)
    try:
        measure(f, c, source_kind="synthetic_native_sample")
    except ValueError as exc:
        assert expected in str(exc), (name, str(exc))
        print("negative", name, str(exc))
    else:
        raise AssertionError("missing rejection: " + name)
