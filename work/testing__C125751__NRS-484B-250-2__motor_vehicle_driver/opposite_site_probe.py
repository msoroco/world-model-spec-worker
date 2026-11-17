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


# Independent saved-source audit for the unselected opposite-turn candidate.
import hashlib
import json
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon
from camera_setup import SIZES

OPPOSITE_CASE = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_left_turn"
CAMERAS = tuple(name + ".mkv" for name in SIZES)

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _read(path):
    return json.loads(Path(path).read_text())

def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def audit_opposite_candidate(attempt, analysis_path):
    """Independently check a saved candidate's original joins and result bindings.

    This is a software audit of a diagnostic candidate. It does not decode or
    review pixels, confirm the Native scene, or accept a legal conclusion.
    """
    attempt, analysis_path = Path(attempt), Path(analysis_path)
    config, result, analysis = (_read(path) for path in
                                (attempt / "config.json", attempt / "result.json", analysis_path))
    if (config.get("selected_case_id") != OPPOSITE_CASE or
            result.get("case_id") != OPPOSITE_CASE or
            analysis.get("case_id") != OPPOSITE_CASE or
            (config.get("law_id"), config.get("cell_id")) != ("NRS-484B-250-2", "C125751") or
            config.get("turning_role") not in ("ego", "other")):
        raise ValueError("Exact opposite-turn candidate identity differs")
    if (result.get("physical_acceptance_claimed") is not False or
            analysis.get("physical_acceptance_claimed") is not False or
            analysis.get("legal_acceptance_claimed") is not False):
        raise ValueError("Candidate analysis must leave acceptance unresolved")
    required = {"config.json", "road_geometry.json", "turn_route_context.json",
                "body_history.jsonl", "crossing_history.jsonl", "signal_context.json",
                "signal_history.jsonl", "stop_context.json", "stop_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS}
    hashes = result.get("source_evidence_hashes")
    if not isinstance(hashes, dict) or set(hashes) != required or analysis.get("source_evidence_hashes") != hashes:
        raise ValueError("Complete candidate source hash inventory required")
    for name, expected in hashes.items():
        source = attempt / name
        if not source.is_file() or _sha(source) != expected:
            raise ValueError("Candidate source hash differs: " + name)
    if (result.get("capture_evidence_sha256") != hashes["capture/evidence.jsonl"] or
            result.get("trace_reference") != "trace.jsonl" or
            result.get("video_frame_map_reference") != "video_frames.jsonl" or
            set(result.get("video_references", [])) != set(CAMERAS)):
        raise ValueError("Candidate result source references differ")
    mapping = _rows(attempt / "video_frames.jsonl")
    if len(mapping) < 2:
        raise ValueError("Candidate needs original frame sequence")
    prior_frame, prior_time = -1, float("-inf")
    for index, row in enumerate(mapping):
        frame, time = row.get("carla_frame"), row.get("time_s")
        if (row.get("video_frame") != index or type(frame) is not int or frame <= prior_frame or
                type(time) not in (int, float) or not math.isfinite(time) or time <= prior_time):
            raise ValueError("Candidate frame map is not monotone")
        prior_frame, prior_time = frame, time
    joins = (("trace.jsonl", "frame", "time_s"),
             ("capture/evidence.jsonl", "original_frame", "recording_time_s"),
             ("crossing_history.jsonl", "frame", "time_s"),
             ("stop_history.jsonl", "frame", "time_s"),
             ("signal_history.jsonl", "frame", "time_s"))
    for name, frame_key, time_key in joins:
        rows = _rows(attempt / name)
        if len(rows) != len(mapping) or any(
                row.get(frame_key) != mapped["carla_frame"] or row.get(time_key) != mapped["time_s"]
                for row, mapped in zip(rows, mapping)):
            raise ValueError("Candidate original frame/time join differs: " + name)
    bodies = _rows(attempt / "body_history.jsonl")
    crossings = _rows(attempt / "crossing_history.jsonl")
    if len(bodies) != len(mapping) or any(
            row.get("native_frame") != mapped["carla_frame"] or
            set(row.get("camera_source_frames", {})) != set(SIZES) or
            any(value != mapped["carla_frame"] for value in row["camera_source_frames"].values()) or
            row.get("actor_sources") != {role: crossed.get(role) for role in ("ego", "other")}
            for row, crossed, mapped in zip(bodies, crossings, mapping)):
        raise ValueError("Candidate paired-body/four-camera frame join differs")
    entry = _read(attempt / "channels/entry_context.json").get("entry_context")
    if not isinstance(entry, dict) or entry != analysis.get("measurements") or entry.get("turning_role") != config["turning_role"]:
        raise ValueError("Candidate saved entry measurement differs")
    road = _read(attempt / "road_geometry.json")
    polygon = Polygon(road.get("intersection_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Candidate source crossing polygon invalid")
    first = {"ego": None, "other": None}
    for mapped, crossed in zip(mapping, crossings):
        for role in first:
            vertices = crossed[role].get("body_vertices_xy_m", [])
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Candidate original body vertices missing")
            if first[role] is None and MultiPoint(vertices).convex_hull.intersects(polygon):
                first[role] = {"frame": mapped["carla_frame"], "time_s": mapped["time_s"]}
    if any(value is None for value in first.values()) or first != entry.get("first_body_entry"):
        raise ValueError("Candidate measured body entry differs from original source")
    turning = config["turning_role"]
    other = "other" if turning == "ego" else "ego"
    if entry.get("turning_minus_other_entry_time_s") != first[turning]["time_s"] - first[other]["time_s"]:
        raise ValueError("Candidate measured entry delta differs")
    signal_rows = {row["frame"]: row for row in _rows(attempt / "signal_history.jsonl")}
    signal_context = _read(attempt / "signal_context.json")
    for role in first:
        source = signal_rows[first[role]["frame"]]
        expected = {"frame": first[role]["frame"], "time_s": first[role]["time_s"],
                    "native_signal_id": signal_context["native_signal_id" if role == "ego" else "other_native_signal_id"],
                    "native_state": source["state" if role == "ego" else "other_state"]}
        if entry.get("signal_at_body_entry", {}).get(role) != expected:
            raise ValueError("Candidate measured signal at body entry differs")
    measured = result.get("measured_values", {})
    if (measured.get("turning_minus_other_entry_time_s") != entry.get("turning_minus_other_entry_time_s") or
            measured.get("signal_at_body_entry") != entry.get("signal_at_body_entry")):
        raise ValueError("Candidate result measurement differs")
    for name, source_name in (("signal_state", "signal_history"), ("stop_state", "stop_history")):
        rows = _rows(attempt / ("channels/" + name + ".jsonl"))
        source = _rows(attempt / (source_name + ".jsonl"))
        if len(rows) != len(mapping) or any(
                row.get("time_s") != original["time_s"] or row.get("value", {}).get("frame") != original["frame"]
                for row, original in zip(rows, source)):
            raise ValueError("Candidate saved channel/source join differs: " + name)
        for row, original in zip(rows, source):
            value = row["value"]
            expected = ({"frame": original["frame"], "ego": original["ego"], "other": original["other"]}
                        if name == "stop_state" else
                        {"frame": original["frame"], "native_signal_id": original["native_signal_id"],
                         "native_state": original["state"],
                         "other_native_signal_id": original["other_native_signal_id"],
                         "other_native_state": original["other_state"]})
            if value != expected:
                raise ValueError("Candidate saved channel value differs: " + name)
    return {"format": "worker-c125751-opposite-candidate-independent-audit-v1",
            "case_id": OPPOSITE_CASE, "frames": len(mapping),
            "result_sha256": _sha(attempt / "result.json"),
            "analysis_sha256": _sha(analysis_path),
            "software_audit_passed": True, "original_pixels_reviewed": False,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


