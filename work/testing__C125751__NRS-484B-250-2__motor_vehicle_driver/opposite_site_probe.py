"""Native opposite-approach discovery candidates for later source review."""
import math


def probe_native_opposite_approaches(world, sample_m=2.0, search_radius_m=25.0):
    """Locate Native same-junction opposing entries for later route/site review.

    A pair here is a topology candidate only. It neither establishes a
    median-opening intersection nor proves a left-turn route or intention.
    """
    if (type(sample_m) not in (int, float) or not math.isfinite(sample_m)
            or type(search_radius_m) not in (int, float)
            or not math.isfinite(search_radius_m)
            or not 0 < sample_m <= 5 or not 0 < search_radius_m <= 50):
        raise ValueError("Finite bounded Native probe spacing/radius required")
    native_map = world.get_map()
    junctions = {}
    for waypoint in native_map.generate_waypoints(sample_m):
        if not waypoint.is_junction:
            continue
        current = waypoint
        upstream = None
        for _ in range(int(search_radius_m / sample_m) + 1):
            predecessors = current.previous(sample_m)
            if len(predecessors) != 1:
                break
            current = predecessors[0]
            if not current.is_junction:
                upstream = current
                break
        if upstream is None:
            continue
        pose = waypoint.transform
        x, y, yaw = (float(pose.location.x), float(pose.location.y),
                     float(pose.rotation.yaw))
        if not all(math.isfinite(value) for value in (x, y, yaw)):
            continue
        junction_id = int(waypoint.get_junction().id)
        lane = (int(upstream.road_id), int(upstream.lane_id))
        junctions.setdefault(junction_id, {}).setdefault(lane, []).append((x, y, yaw))
    candidates = []
    for junction_id, lanes in sorted(junctions.items()):
        lane_ids = sorted(lanes)
        for index, first_lane in enumerate(lane_ids):
            for second_lane in lane_ids[index + 1:]:
                matches = []
                for first in lanes[first_lane]:
                    for second in lanes[second_lane]:
                        distance = math.hypot(first[0] - second[0], first[1] - second[1])
                        angle = abs((second[2] - first[2] + 180) % 360 - 180)
                        if distance <= search_radius_m and angle >= 160:
                            matches.append((distance, -angle, first, second))
                if not matches:
                    continue
                distance, negative_angle, first, second = min(matches)
                candidates.append({
                    "native_map_name": native_map.name,
                    "native_junction_id": junction_id,
                    "approach_road_lanes": [list(first_lane), list(second_lane)],
                    "junction_sample_xy_yaw": [list(first), list(second)],
                    "sample_separation_m": distance,
                    "approach_angle_deg": -negative_angle,
                    "probe_spacing_m": sample_m,
                    "review_status": "candidate_only",
                    "unresolved": ["median-opening and statutory intersection identity",
                                   "source-reviewed routes and left-turn exit",
                                   "original approach, intention and trajectory evidence"],
                })
    return candidates
