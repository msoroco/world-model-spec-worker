"""Native opposite-approach discovery candidates for later source review."""
import math


def _route_exits(entry, upstream, step_m, radius_m):
    """Trace bounded Native branches into left and straight route candidates."""
    start = entry.transform
    start_yaw = float(start.rotation.yaw)
    start_xy = (float(start.location.x), float(start.location.y))
    junction_id = int(entry.get_junction().id)
    if not all(math.isfinite(v) for v in (*start_xy, start_yaw)):
        return {"left": [], "straight": []}
    upstream_pose = upstream.transform
    upstream_xy = (float(upstream_pose.location.x), float(upstream_pose.location.y))
    if not all(math.isfinite(v) for v in upstream_xy):
        return {"left": [], "straight": []}
    exits = {"left": {}, "straight": {}}
    frontier = [(entry, 0, [list(upstream_xy), list(start_xy)])]
    seen = set()
    max_steps = int(radius_m / step_m) + 2
    while frontier:
        current, depth, route = frontier.pop(0)
        if depth >= max_steps or id(current) in seen:
            continue
        seen.add(id(current))
        for successor in current.next(step_m):
            pose = successor.transform
            x, y, yaw = (float(pose.location.x), float(pose.location.y),
                         float(pose.rotation.yaw))
            if not all(math.isfinite(v) for v in (x, y, yaw)):
                continue
            if math.hypot(x - start_xy[0], y - start_xy[1]) > radius_m:
                continue
            if successor.is_junction:
                if int(successor.get_junction().id) == junction_id:
                    frontier.append((successor, depth + 1, route + [[x, y]]))
                continue
            turn = (yaw - start_yaw + 180) % 360 - 180
            kind = "left" if 45 <= turn <= 135 else "straight" if abs(turn) <= 30 else None
            if kind is not None:
                key = (int(successor.road_id), int(successor.lane_id))
                value = {"exit_road_lane": list(key),
                         "exit_xy_yaw": [x, y, yaw],
                         "turn_angle_deg": turn,
                         "route_xy": route + [[x, y]]}
                if key not in exits[kind] or len(value["route_xy"]) < len(exits[kind][key]["route_xy"]):
                    exits[kind][key] = value
    return {kind: [exits[kind][key] for key in sorted(exits[kind])]
            for kind in ("left", "straight")}


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
        junctions.setdefault(junction_id, {}).setdefault(lane, []).append((x, y, yaw, waypoint, upstream))
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
                distance, negative_angle, first, second = min(
                    matches, key=lambda match: (match[0], match[1],
                                                 match[2][:3], match[3][:3]))
                route_exits = [_route_exits(first[3], first[4], sample_m, search_radius_m),
                               _route_exits(second[3], second[4], sample_m, search_radius_m)]
                candidates.append({
                    "native_map_name": native_map.name,
                    "native_junction_id": junction_id,
                    "approach_road_lanes": [list(first_lane), list(second_lane)],
                    "junction_sample_xy_yaw": [list(first[:3]), list(second[:3])],
                    "left_turn_exit_candidates": [item["left"] for item in route_exits],
                    "straight_exit_candidates": [item["straight"] for item in route_exits],
                    "sample_separation_m": distance,
                    "approach_angle_deg": -negative_angle,
                    "probe_spacing_m": sample_m,
                    "review_status": "candidate_only",
                    "unresolved": ["median-opening and statutory intersection identity",
                                   "source-reviewed route, exit and turn feasibility",
                                   "original approach, intention and trajectory evidence"],
                })
    return candidates


def route_pair_from_candidate(candidate, turning_role, left_index=0, straight_index=0):
    """Build a candidate site input for the two-vehicle geometry checker.

    A caller must review the original Native map/site before adopting this as
    a selected construction. The indices make branch selection explicit.
    """
    if candidate.get("review_status") != "candidate_only" or turning_role not in ("ego", "other"):
        raise ValueError("Unreviewed Native candidate and turning role required")
    if type(left_index) is not int or type(straight_index) is not int or min(left_index, straight_index) < 0:
        raise ValueError("Nonnegative route branch indices required")
    roles = ("ego", "other")
    turn_position = roles.index(turning_role)
    straight_position = 1 - turn_position
    try:
        left = candidate["left_turn_exit_candidates"][turn_position][left_index]
        straight = candidate["straight_exit_candidates"][straight_position][straight_index]
        routes = {turning_role: left["route_xy"],
                  roles[straight_position]: straight["route_xy"]}
        lanes = dict(zip(roles, candidate["approach_road_lanes"]))
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("Both Native route branches required") from exc
    from opposite_turn_construction import check_routes
    geometry = check_routes(routes, turning_role)
    return {"native_map_name": candidate["native_map_name"],
            "native_junction_id": candidate["native_junction_id"],
            "routes": routes,
            "expected_approach_lanes": lanes,
            "geometry": geometry,
            "review_status": "candidate_only"}
