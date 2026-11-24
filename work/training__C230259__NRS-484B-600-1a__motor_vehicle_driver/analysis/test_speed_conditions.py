"""CPU diagnostic for source joins and missing-input rejection."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from speed_conditions import measure


def fixture():
    return [{
        "frame_id": i, "sim_time_s": i / 20,
        "camera_frames": {name: i for name in ("front", "rear", "left", "right")},
        "ego_velocity_mps": [8.0, 0.0, 0.0],
        "participants": [{"id": "traffic-1", "velocity_mps": [6.0, 0.0, 0.0]}],
        "lane_width_m": 3.5, "surface": {"kind": "pavement"},
        "weather": {"precipitation": 0.0, "visibility_m": 200.0},
    } for i in range(600)]


frames = fixture()
result = measure(frames, source_kind="synthetic_native_sample")
assert result["duration_s"] == 30.0
assert result["ego_speed_mps"] == {"minimum": 8.0, "maximum": 8.0, "mean": 8.0}
assert result["legal_judgment"] == "unresolved"
print("positive", json.dumps(result, sort_keys=True))

for name, mutate, expected in [
    ("camera", lambda f: f[17]["camera_frames"].pop("right"), "missing four source-camera frame joins"),
    ("weather", lambda f: f[18].pop("weather"), "missing weather or visibility context"),
    ("traffic", lambda f: f[19].pop("participants"), "missing contemporaneous traffic"),
    ("duration", lambda f: f.pop(), "capture shorter than minimum frame count"),
]:
    candidate = copy.deepcopy(frames)
    mutate(candidate)
    try:
        measure(candidate, source_kind="synthetic_native_sample")
    except ValueError as exc:
        assert expected in str(exc), (name, str(exc))
        print("negative", name, str(exc))
    else:
        raise AssertionError("missing negative rejection: " + name)
