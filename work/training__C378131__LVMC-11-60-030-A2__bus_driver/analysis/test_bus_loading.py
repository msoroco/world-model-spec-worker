"""Positive and missing-source CPU probes; never original Native proof."""
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bus_loading import measure


def fixture():
    frames = [{
        "frame_id": i, "sim_time_s": i / 20,
        "camera_frames": {name: i for name in ("front", "rear", "left", "right")},
        "bus_speed_mps": 0.0 if 100 <= i < 200 else 5.0,
        "passenger_door_open": 120 <= i < 180,
        "boardings": 1 if i == 130 else 0,
        "occupied_zone_id": "terminus-1",
    } for i in range(600)]
    context = {"vehicle_class": "route_bus_non_tour", "route_id": "R-1", "street_id": "S-1",
               "zone": {"kind": "route_destination", "id": "terminus-1", "route_id": "R-1",
                        "designation_source": {"path": "authority/route-R-1.json", "sha256": "a" * 64}},
               "emergency_source": None}
    return frames, context


frames, context = fixture()
result = measure(frames, context, source_kind="synthetic_native_sample")
assert result["stopped_frames"] == 100
assert result["door_open_stopped_zone_frames"] == 60
assert result["observed_boardings"] == 1
assert result["legal_judgment"] == "unresolved"
print("positive", json.dumps(result, sort_keys=True))

for name, mutate, error in [
    ("camera", lambda f, c: f[130]["camera_frames"].pop("right"), "four source-camera"),
    ("door", lambda f, c: f[130].pop("passenger_door_open"), "passenger-door"),
    ("authority", lambda f, c: c["zone"].pop("designation_source"), "designation authority"),
    ("route", lambda f, c: c["zone"].update(route_id="R-2"), "assigned route"),
    ("emergency", lambda f, c: c.pop("emergency_source"), "emergency context"),
    ("duration", lambda f, c: f.pop(), "shorter than 30 seconds"),
]:
    f, c = copy.deepcopy(frames), copy.deepcopy(context)
    mutate(f, c)
    try:
        measure(f, c, source_kind="synthetic_native_sample")
    except ValueError as exc:
        assert error in str(exc), (name, str(exc))
        print("negative", name, str(exc))
    else:
        raise AssertionError("missing rejection: " + name)
