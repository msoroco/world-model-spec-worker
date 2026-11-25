"""Bind a reviewed C125697 median-opening source to mapped crossing routes.

The reviewed packet is an input to a later Native attempt. It is never a
substitute for observing entry timing or deciding a right-of-way judgment.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import entry_timing
import footprint_capture


def _require(value, message):
    if not value:
        raise ValueError(message)


def _inside(point, bounds):
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def _direction(route):
    dx = route[1][0] - route[0][0]
    dy = route[1][1] - route[0][1]
    norm = math.hypot(dx, dy)
    _require(norm > 0, "zero-length approach direction")
    return dx / norm, dy / norm


def _approach_sides(ego_route, other_route):
    ego = _direction(ego_route)
    other = _direction(other_route)
    signed = ego[0] * other[1] - ego[1] * other[0]
    _require(abs(signed) >= 0.5, "approaches are not crossing from left and right")
    return ("left", "right") if signed < 0 else ("right", "left")


def validate_scene(scene, opendrive_text, location_factory=None, world_map=None):
    """Reject unreviewed geometry, changed map and incorrect approach sides."""
    _require(scene.get("review_status") == "reviewed_original" and scene.get("reviewer"),
             "reviewed original site required")
    _require(scene.get("cell_id") == "C125697" and
             scene.get("actor") == "motor_vehicle_driver" and
             scene.get("law_id") == "NRS-484B-250-2", "wrong reviewed identity")
    _require(scene.get("ego_highway") and scene.get("other_highway") and
             scene["ego_highway"] != scene["other_highway"],
             "two different reviewed public highways required")
    crossing = scene.get("crossing", {})
    bounds = crossing.get("bounds_xy_m")
    _require(crossing.get("kind") == "median_opening_roadway_crossing" and
             crossing.get("id"), "identified median roadway crossing required")
    _require(isinstance(bounds, list) and len(bounds) == 4 and
             all(type(v) in (int, float) and math.isfinite(v) for v in bounds) and
             bounds[0] < bounds[2] and bounds[1] < bounds[3],
             "finite original crossing bounds required")
    _require(hashlib.sha256(opendrive_text.encode()).hexdigest() ==
             crossing.get("opendrive_sha256"), "live OpenDRIVE differs from reviewed source")
    routes = {}
    for name in ("ego", "other"):
        route = scene.get(name + "_route_xy_m")
        _require(isinstance(route, list) and len(route) >= 3 and
                 all(isinstance(p, list) and len(p) == 2 and
                     all(type(v) in (int, float) and math.isfinite(v) for v in p)
                     for p in route), "finite mapped " + name + " route required")
        _require(not _inside(route[0], bounds) and not _inside(route[-1], bounds) and
                 any(_inside(p, bounds) for p in route[1:-1]),
                 name + " route must traverse reviewed crossing")
        routes[name] = route
    sides = _approach_sides(routes["ego"], routes["other"])
    _require(scene.get("ego_approach_side") == sides[0] and
             scene.get("other_approach_side") == sides[1],
             "declared left/right approach differs from route geometry")
    _require(scene.get("ego_approach_road_id") != scene.get("other_approach_road_id"),
             "distinct approach road IDs required")
    signal = scene.get("governing_signal", {})
    _require(signal.get("kind") == "official_traffic_signal" and
             signal.get("readback_state") == "inoperative" and
             signal.get("controls_traffic") is False,
             "reviewed inoperative governing signal and control readback required")
    _require(set(signal.get("controlled_approach_road_ids", [])) == {
             scene.get("ego_approach_road_id"), scene.get("other_approach_road_id")},
             "governing signal does not bind both approaches")
    _require(scene.get("opposing_left_turn_excluded_source") and
             scene.get("subsection_4_applicability_review"),
             "opposing-turn and subsection 4 source review required")
    if world_map is not None:
        _require(location_factory is not None, "Native location factory required")
        for name in ("ego", "other"):
            bound = []
            for x, y in routes[name]:
                waypoint = world_map.get_waypoint(location_factory(x, y), project_to_road=False)
                _require(waypoint is not None and math.hypot(
                         waypoint.transform.location.x - x,
                         waypoint.transform.location.y - y) <= 2,
                         name + " route is off mapped lane")
                bound.append(waypoint)
            _require(bound[0].road_id == scene[name + "_approach_road_id"] and
                     any(w.is_junction for w in bound[1:-1]),
                     name + " route road or junction readback failed")
    return {"crossing_id": crossing["id"], "approach_sides": sides}


def _source(packet_dir, ref, name):
    _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256") and
             ref.get("citation"), "reviewed " + name + " source reference required")
    candidate = packet_dir / ref["path"]
    path = candidate.resolve()
    _require(not candidate.is_symlink() and path.is_relative_to(packet_dir) and path.is_file(),
             "reviewed " + name + " source missing")
    data = path.read_bytes()
    _require(hashlib.sha256(data).hexdigest() == ref["sha256"],
             "reviewed " + name + " source changed")
    return data


def reviewed_packet(packet_path, world_map, location_factory):
    packet_path = Path(packet_path)
    _require(not packet_path.is_symlink() and packet_path.is_file(),
             "reviewed original site packet missing")
    packet_dir = packet_path.parent.resolve()
    scene = json.loads(packet_path.read_text())
    opendrive = world_map.to_opendrive()
    validate_scene(scene, opendrive, location_factory, world_map)
    refs = scene.get("source_refs", {})
    devices = _source(packet_dir, refs.get("device_inventory"), "device inventory")
    highways = _source(packet_dir, refs.get("highway_identity"), "highway identity")
    device_record = json.loads(devices)
    highway_record = json.loads(highways)
    signal = scene["governing_signal"]
    _require(device_record.get("governing_signal_actor_id") == signal.get("actor_id") and
             device_record.get("controlled_approach_road_ids") ==
             signal.get("controlled_approach_road_ids"),
             "governing-device inventory differs from original site")
    _require(highway_record.get("ego_highway") == scene["ego_highway"] and
             highway_record.get("other_highway") == scene["other_highway"] and
             highway_record.get("public_access_confirmed") is True,
             "public-highway identity source differs from original site")
    return scene, {"opendrive": opendrive.encode(),
                   "device_inventory": devices, "highway_identity": highways}


def construct_native(world, scene, location_factory, blueprint_library, signal_readback):
    """Spawn the two reviewed mapped vehicles with rollback on partial failure."""
    validate_scene(scene, world.get_map().to_opendrive(), location_factory, world.get_map())
    _require(signal_readback(scene["governing_signal"]) == "inoperative",
             "live governing signal is not inoperative")
    actors = {}
    try:
        for name in ("ego", "other"):
            blueprint_id = scene.get(name + "_blueprint")
            _require(isinstance(blueprint_id, str) and blueprint_id.startswith("vehicle."),
                     "conventional motor-vehicle blueprint required")
            blueprint = blueprint_library.find(blueprint_id)
            x, y = scene[name + "_route_xy_m"][0]
            waypoint = world.get_map().get_waypoint(location_factory(x, y), project_to_road=False)
            actor = world.try_spawn_actor(blueprint, waypoint.transform)
            _require(actor is not None, name + " original vehicle spawn failed")
            actors[name] = actor
        return actors
    except BaseException:
        for actor in reversed(tuple(actors.values())):
            actor.destroy()
        raise


def measure_saved(trace, scene, expected_frames=900):
    """Measure both crossing entries from sealed original Native body history."""
    _require(trace.get("case_id") == scene.get("case_id") and
             trace.get("map_sha256") == scene["crossing"]["opendrive_sha256"],
             "saved trace case or original map mismatch")
    frames = trace.get("frames")
    _require(isinstance(frames, list) and len(frames) == expected_frames,
             "complete original frame history required")
    _require(set(trace.get("actor_ids", {})) == {"ego", "other"} and
             trace["actor_ids"]["ego"] != trace["actor_ids"]["other"],
             "two distinct original actor IDs required")
    bounds = scene["crossing"]["bounds_xy_m"]
    polygon = [(bounds[0], bounds[1]), (bounds[2], bounds[1]),
               (bounds[2], bounds[3]), (bounds[0], bounds[3])]
    first_frame = None
    first_time = None
    packet_frames = []
    for index, frame in enumerate(frames):
        native_frame = frame.get("native_frame_id")
        native_time = frame.get("native_elapsed_seconds")
        _require(type(native_frame) is int and type(native_time) in (int, float) and
                 math.isfinite(native_time), "original Native frame/clock missing")
        if first_frame is None:
            first_frame, first_time = native_frame, native_time
        _require(native_frame == first_frame + index and
                 math.isclose(native_time - first_time, index / 20, abs_tol=.002),
                 "original Native frame/clock discontinuity")
        _require(frame.get("frame") == index and
                 math.isclose(frame.get("time_s", -1), index / 20, abs_tol=1e-5),
                 "attempt-relative frame/time join incomplete")
        _require(frame.get("signal_readback") == "inoperative",
                 "governing signal changed during original history")
        states = {}
        for name in ("ego", "other"):
            actor = frame.get(name, {})
            _require(actor.get("id") == trace["actor_ids"][name] and
                     type(actor.get("road_id")) is int,
                     "original actor or mapped road identity changed")
            body = actor.get("body_vertices_xy_m")
            _require(isinstance(body, list) and len(body) == 4 and
                     all(isinstance(p, list) and len(p) == 2 and
                         all(type(v) in (int, float) and math.isfinite(v) for v in p)
                         for p in body), "original vehicle body footprint missing")
            if index == 0:
                _require(actor["road_id"] == scene[name + "_approach_road_id"],
                         "original approach road readback changed")
            states[name] = {"footprint_intersects_intersection":
                            footprint_capture.intersects_convex([tuple(p) for p in body], polygon)}
        packet_frames.append({"frame": native_frame, "timestamp_s": native_time,
                              "actors": states})
    packet = {
        "format": "nrs-484b-250-2-original-frames-v1", "law_id": "NRS-484B-250-2",
        "cell_id": "C125697", "case_id": scene["case_id"],
        "participants": {
            name: {"kind": "motor_vehicle", "road_id": scene[name + "_highway"],
                   "approach_side": scene[name + "_approach_side"], "movement": "straight"}
            for name in ("ego", "other")},
        "opposite_approaches": False, "official_device_controls_intersection": False,
        "signal": {"present": True, "mode": "inoperative", "controls_traffic": False},
        "frames": packet_frames,
    }
    observation = entry_timing.measure(packet)
    prior_inside = {"ego": False, "other": False}
    exits = {"ego": None, "other": None}
    for row in packet_frames:
        for name in ("ego", "other"):
            inside = row["actors"][name]["footprint_intersects_intersection"]
            if prior_inside[name] and not inside and exits[name] is None:
                exits[name] = {"frame": row["frame"],
                               "timestamp_s": row["timestamp_s"]}
            prior_inside[name] = inside
    observation["ego_exit"] = exits["ego"]
    observation["other_exit"] = exits["other"]
    observation["ego_entered_after_other_exit"] = (
        None if exits["other"] is None else
        observation["ego_entry"]["upper_frame"] >= exits["other"]["frame"])
    observation["native_first_frame_id"] = first_frame
    observation["native_first_elapsed_seconds"] = first_time
    return observation


def audit_saved_sources(root, manifest, scene, *, diagnostic_fixture=False):
    """Reject missing or stale original actor, map, device and camera sources."""
    expected_frames = manifest.get("frame_count") if diagnostic_fixture else 900
    _require(expected_frames in ((9, 900) if diagnostic_fixture else (900,)),
             "unsupported original frame count")
    _require(manifest.get("case_id") == scene.get("case_id") and
             manifest.get("frame_count") == expected_frames,
             "source manifest case or frame count mismatch")
    camera_names = ("overview", "approach", "reference_corner", "driver_reference")
    required = {"native_trace", "opendrive", "device_inventory", "highway_identity"} | {
        "camera_" + name for name in camera_names}
    refs = manifest.get("sources", {})
    _require(set(refs) == required, "missing or extraneous original source")
    root = Path(root).resolve()
    hashes = {}
    for name in sorted(required):
        ref = refs[name]
        _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"),
                 "original source reference incomplete: " + name)
        candidate = root / ref["path"]
        path = candidate.resolve()
        _require(not candidate.is_symlink() and path.is_relative_to(root) and path.is_file(),
                 "missing original source: " + name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        _require(digest == ref["sha256"], "stale original source: " + name)
        hashes[name] = digest
    _require(hashes["opendrive"] == scene["crossing"]["opendrive_sha256"],
             "original map differs from construction source")
    if not diagnostic_fixture:
        opendrive = (root / refs["opendrive"]["path"]).read_text()
        validate_scene(scene, opendrive)
        for name in ("device_inventory", "highway_identity"):
            source_ref = scene.get("source_refs", {}).get(name, {})
            _require(source_ref.get("sha256") == hashes[name] and
                     source_ref.get("citation"),
                     "reviewed original " + name + " reference differs")
        device = json.loads((root / refs["device_inventory"]["path"]).read_text())
        highway = json.loads((root / refs["highway_identity"]["path"]).read_text())
        _require(device.get("governing_signal_actor_id") ==
                 scene["governing_signal"].get("actor_id") and
                 device.get("controlled_approach_road_ids") ==
                 scene["governing_signal"].get("controlled_approach_road_ids"),
                 "original governing-device inventory changed")
        _require(highway.get("ego_highway") == scene["ego_highway"] and
                 highway.get("other_highway") == scene["other_highway"] and
                 highway.get("public_access_confirmed") is True,
                 "original public-highway source changed")
    trace = json.loads((root / refs["native_trace"]["path"]).read_text())
    observation = measure_saved(trace, scene, expected_frames)
    return {"source_sha256": hashes, "observations": observation,
            "physical_pixels_reviewed": False, "legal_judgment": "unresolved"}
