"""Independent geometric completion check from original actor positions."""
from __future__ import annotations

import math

from emergency_scene import scene_geometry


def assess_motion(rows: list[dict] | None, site: dict | None) -> dict:
    """Measure an approach; never infer statutory permission or audibility."""
    method = "900 Native actor poses, site direction, path progress and recipient distance"
    if not rows or not site:
        return {"status": "unverified", "method": method,
                "sources": ["actor_trace.jsonl", "site_packet.json"],
                "reason": "Original actor or reviewed site source missing"}
    if len(rows) != 900 or any(row.get("frame") != index for index, row in enumerate(rows)):
        raise ValueError("Original actor frame sequence incomplete")
    geometry = scene_geometry(site.get("approach"),
                              site.get("intersection_station_m", 0.0))
    sign = 1 if geometry["approach"] == "eastbound" else -1
    ego_id = rows[0]["ego"]["actor_id"]
    pedestrian_id = rows[0]["pedestrian"]["actor_id"]
    if ego_id == pedestrian_id or any(
            row["ego"]["actor_id"] != ego_id or
            row["pedestrian"]["actor_id"] != pedestrian_id for row in rows):
        raise ValueError("Original participant identity changed")
    ego_start = rows[0]["ego"]
    ego_end = rows[-1]["ego"]
    pedestrian = rows[0]["pedestrian"]
    progress_m = sign * (ego_end["x_m"] - ego_start["x_m"])
    pass_m = sign * (ego_end["x_m"] - pedestrian["x_m"])
    closest_m = min(math.hypot(row["ego"]["x_m"] - row["pedestrian"]["x_m"],
                               row["ego"]["y_m"] - row["pedestrian"]["y_m"])
                    for row in rows)
    lane_y = geometry["ego_spawn_xy_m"][1]
    lateral_error_m = max(abs(row["ego"]["y_m"] - lane_y) for row in rows)
    valid = (progress_m >= 70 and pass_m >= 10 and closest_m <= 10 and
             lateral_error_m <= 2 and
             abs(ego_start["x_m"] - geometry["ego_spawn_xy_m"][0]) <= 1 and
             abs(pedestrian["x_m"] - geometry["pedestrian_spawn_xy_m"][0]) <= 1)
    return {"status": "met" if valid else "not_met", "method": method,
            "sources": ["actor_trace.jsonl", "site_packet.json"],
            "ego_actor_id": ego_id, "pedestrian_actor_id": pedestrian_id,
            "progress_m": progress_m, "passed_recipient_station_m": pass_m,
            "closest_recipient_distance_m": closest_m,
            "maximum_lane_lateral_error_m": lateral_error_m}
