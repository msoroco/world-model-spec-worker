"""Positive/negative source-bound 30-second sidewalk measurement fixture."""
import hashlib
import json
from pathlib import Path
from sidewalk_occupancy import FRAME_COUNT, FRAME_RATE, measure_frame, measure_sources

root = Path(".runtime-work/c229977-sidewalk-measurement")
root.mkdir(parents=True, exist_ok=True)
mp = root / "map.json"
tp = root / "trace.json"
map_packet = {
    "map_acquisition": "synthetic_native_sample",
    "highway_boundary_source": "synthetic_native_sample",
    "property_boundary_source": "synthetic_native_sample",
    "intended_pedestrian_use_source": "synthetic_native_sample",
    "sidewalk_polygon_m": [[0, 0], [20, 0], [20, 3], [0, 3]],
}
outside = [[5, -3], [7, -3], [7, -1], [5, -1]]
partial = [[5, -1], [7, -1], [7, 1], [5, 1]]
inside = [[5, 0.4], [7, 0.4], [7, 2.4], [5, 2.4]]
rows = [{
    "frame": i, "time_s": i / FRAME_RATE,
    "actor_pose_source": "synthetic_native_sample",
    "velocity_source": "synthetic_native_sample",
    "speed_mps": 0.0 if 100 <= i < 500 else 2.0,
    "vehicle_footprint_m": outside if i < 100 else partial if i < 300 else inside,
} for i in range(FRAME_COUNT)]
def put(path, obj):
    path.write_text(json.dumps(obj, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()
mh, th = put(mp, map_packet), put(tp, rows)
m = measure_sources(mp, mh, tp, th)
assert m["rest_frames"] == 400
assert m["rest_and_overlap_frames"] == 400
assert m["entire_footprint_rest_frames"] == 200
assert m["legal_conclusion"] is None
assert abs(measure_frame(partial, map_packet["sidewalk_polygon_m"])["vehicle_overlap_fraction"] - .5) < 1e-9
assert not measure_frame(outside, map_packet["sidewalk_polygon_m"])["overlap_positive"]
def reject(fn, phrase):
    try: fn()
    except ValueError as exc: assert phrase in str(exc), str(exc)
    else: raise AssertionError("expected rejection: " + phrase)
reject(lambda: measure_sources(mp, "0" * 64, tp, th), "source hash")
bad = [dict(r) for r in rows]; bad[200]["time_s"] = 17
bad_h = put(tp, bad)
reject(lambda: measure_sources(mp, mh, tp, bad_h), "20 Hz")
bad = [dict(r) for r in rows]; bad[200]["actor_pose_source"] = ""
bad_h = put(tp, bad)
reject(lambda: measure_sources(mp, mh, tp, bad_h), "raw actor")
bad = [dict(r) for r in rows]; bad[200]["vehicle_footprint_m"] = [[0, 0]] * 4
bad_h = put(tp, bad)
reject(lambda: measure_sources(mp, mh, tp, bad_h), "degenerate")
th = put(tp, rows)
map_bad = dict(map_packet, intended_pedestrian_use_source="")
bad_mh = put(mp, map_bad)
reject(lambda: measure_sources(mp, bad_mh, tp, th), "context source provenance")
print("PASS source-bound 600-frame/20Hz sidewalk overlap, halt history, geometry and provenance negatives")
