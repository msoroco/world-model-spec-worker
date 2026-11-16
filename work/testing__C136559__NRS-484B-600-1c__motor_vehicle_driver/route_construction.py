"""Select an unbranched Native lane corridor from source-reviewed road IDs.

The selected IDs and alley/access-aisle classification must be independently
source-reviewed. This helper verifies lane continuity and measured route length;
it does not declare public-way status or guarantee 80 mph is physically attained.
"""

import math


def _distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def select_corridor(native_map, starts, *, reviewed_road_id, reviewed_lane_id,
                    minimum_length_m, step_m=5.0):
    if not isinstance(reviewed_road_id, int) or not isinstance(reviewed_lane_id, int):
        raise ValueError("Source-reviewed Native road and lane IDs required")
    if not math.isfinite(minimum_length_m) or minimum_length_m <= 0 or not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("Positive finite engineering corridor lengths required")
    candidates = []
    for start in starts:
        waypoint = native_map.get_waypoint(start.location, project_to_road=False)
        if waypoint is None or waypoint.road_id != reviewed_road_id or waypoint.lane_id != reviewed_lane_id or waypoint.is_junction:
            continue
        path = [waypoint]
        length = 0.0
        for _ in range(math.ceil(minimum_length_m / step_m) + 10):
            successors = [wp for wp in path[-1].next(step_m)
                          if wp.road_id == reviewed_road_id and wp.lane_id == reviewed_lane_id and not wp.is_junction]
            if len(successors) != 1:
                break
            next_wp = successors[0]
            segment = _distance(path[-1].transform.location, next_wp.transform.location)
            if not math.isfinite(segment) or segment <= 0:
                break
            length += segment
            path.append(next_wp)
            if length >= minimum_length_m:
                candidates.append({"start": start, "waypoints": path,
                                   "measured_length_m": length,
                                   "road_id": reviewed_road_id,
                                   "lane_id": reviewed_lane_id})
                break
    if not candidates:
        raise ValueError("No source-reviewed Native corridor meets requested length")
    return max(candidates, key=lambda candidate: candidate["measured_length_m"])
