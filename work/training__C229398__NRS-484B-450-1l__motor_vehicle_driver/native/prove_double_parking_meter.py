"""CPU diagnostic proof for original-footprint parking meter; no Native claim."""
from __future__ import annotations

import json
from pathlib import Path

from double_parking_meter import measure


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURE = ROOT / ".runtime-work" / "c229398-double-parking-meter"
FIXTURE.mkdir(parents=True, exist_ok=True)
MAP = FIXTURE / "surveyed-map.json"
MAP.write_text(json.dumps({
    "source_kind": "surveyed_map_geometry",
    "curb_start_xy_m": [0, 0],
    "curb_end_xy_m": [100, 0],
    "road_interior_normal_sign": 1,
}) + "\n")


def body(x, y):
    return [[x - 2, y - 0.8], [x + 2, y - 0.8], [x + 2, y + 0.8], [x - 2, y + 0.8]]


def write(name, ego_x, ego_y, curb_x=30, curb_y=1.5, malformed=False):
    path = FIXTURE / (name + ".jsonl")
    with path.open("w") as stream:
        for i in range(600):
            ex = ego_x + (i * 0.1 if name == "moving" else 0)
            row = {
                "source_kind": "original_actor_body_footprints",
                "frame": i,
                "time_s": i / 20,
                "actors": {
                    "ego": {"footprint_corners_xy_m": body(ex, ego_y)},
                    "curbside": {"footprint_corners_xy_m": body(curb_x, curb_y)},
                },
            }
            if malformed and i == 200:
                del row["actors"]["curbside"]
            stream.write(json.dumps(row) + "\n")
    return path


active = measure(MAP, write("active", 30, 4.0))
assert active["frame_count"] == 600
assert active["concurrent_overlap_at_rest_frame_count"] == 599
assert active["longest_concurrent_run_frames"] == 599
assert active["max_longitudinal_overlap_m"] == 4.0
assert active["legal_exception_or_compliance_determined"] is False

no_overlap = measure(MAP, write("no_overlap", 40, 4.0))
assert no_overlap["concurrent_overlap_at_rest_frame_count"] == 0
wrong_side = measure(MAP, write("wrong_side", 30, 0.25))
assert wrong_side["concurrent_overlap_at_rest_frame_count"] == 0
moving = measure(MAP, write("moving", 30, 4.0))
assert moving["concurrent_overlap_at_rest_frame_count"] == 0

try:
    measure(MAP, write("missing_source", 30, 4.0, malformed=True))
except ValueError as error:
    assert "Both original actor bodies required" in str(error)
else:
    raise AssertionError("Missing original actor source was accepted")

bad_timing = write("bad_timing", 30, 4.0)
lines = bad_timing.read_text().splitlines()
row = json.loads(lines[300])
row["time_s"] += 0.05
lines[300] = json.dumps(row)
bad_timing.write_text("\n".join(lines) + "\n")
try:
    measure(MAP, bad_timing)
except ValueError as error:
    assert "Source frame timing mismatch" in str(error)
else:
    raise AssertionError("Broken original frame join was accepted")

print(json.dumps({
    "passed": True,
    "source_only": True,
    "active_frames": active["concurrent_overlap_at_rest_frame_count"],
    "no_overlap_frames": no_overlap["concurrent_overlap_at_rest_frame_count"],
    "wrong_side_frames": wrong_side["concurrent_overlap_at_rest_frame_count"],
    "moving_frames": moving["concurrent_overlap_at_rest_frame_count"],
    "missing_source_rejected": True,
    "broken_time_join_rejected": True,
    "physical_realization_verified": False,
}, indent=2))
