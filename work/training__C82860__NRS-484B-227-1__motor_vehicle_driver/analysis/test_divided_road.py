"""CPU fixture for geometry comparison and missing-source rejections."""
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from divided_road import measure


def square(x, y, half=0.1):
    return [[x - half, y - half], [x + half, y - half], [x + half, y + half], [x - half, y + half]]


def fixture(crossing_x):
    map_context = {
        "layout": "divided_road",
        "median_polygon": [[-5, -1], [5, -1], [5, 1], [-5, 1]],
        "opening_polygon": [[-1, -1], [1, -1], [1, 1], [-1, 1]],
        "right_roadway_polygon": [[-5, -5], [5, -5], [5, -1], [-5, -1]],
        "opposite_roadway_polygon": [[-5, 1], [5, 1], [5, 5], [-5, 5]],
        "opening_authority_source": {"path": "survey/authority.json", "sha256": "b" * 64},
    }
    frames = []
    for i in range(600):
        y = -3 + 6 * i / 599
        frames.append({"frame_id": i, "sim_time_s": i / 20,
                       "camera_frames": {name: i for name in ("front", "rear", "left", "right")},
                       "ego_footprint": square(crossing_x, y), "ego_heading_deg": 90.0})
    return frames, map_context


opening_frames, map_context = fixture(0.0)
opening_result = measure(opening_frames, map_context, source_kind="synthetic_native_sample")
barrier_frames, barrier_context = fixture(3.0)
barrier_result = measure(barrier_frames, barrier_context, source_kind="synthetic_native_sample")
assert opening_result["opening_overlap_frames"] > 0
assert barrier_result["opening_overlap_frames"] == 0
assert barrier_result["median_without_opening_overlap_frames"] > 0
assert opening_result["authority_verified"] is False
assert opening_result["legal_judgment"] == "unresolved"
print("opening", json.dumps(opening_result, sort_keys=True))
print("barrier", json.dumps(barrier_result, sort_keys=True))

for name, mutate, expected in [
    ("camera", lambda f, c: f[130]["camera_frames"].pop("right"), "four source-camera"),
    ("geometry", lambda f, c: c.pop("median_polygon"), "median polygon"),
    ("authority", lambda f, c: c.pop("opening_authority_source"), "public-authority source"),
    ("footprint", lambda f, c: f[130].pop("ego_footprint"), "ego footprint polygon"),
    ("timing", lambda f, c: f[130].update(sim_time_s=7.0), "20 Hz frame timing gap"),
    ("duration", lambda f, c: f.pop(), "capture shorter than 30 seconds"),
]:
    frames, context = copy.deepcopy(opening_frames), copy.deepcopy(map_context)
    mutate(frames, context)
    try:
        measure(frames, context, source_kind="synthetic_native_sample")
    except ValueError as exc:
        assert expected in str(exc), (name, str(exc))
        print("negative", name, str(exc))
    else:
        raise AssertionError("missing rejection: " + name)
