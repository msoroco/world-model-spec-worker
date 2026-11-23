"""Source-gated median-opening construction and saved physical observations.

This module makes no legal right-of-way decision. CARLA is bound lazily by the
caller, after the inspected OpenDRIVE source and governing signal are checked.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _point_inside(point, box):
    x, y = point
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def validate_scene(scene, opendrive_text):
    crossing = scene["crossing"]
    box = crossing["bounds_xy_m"]
    if len(box) != 4 or not all(math.isfinite(v) for v in box) or box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("invalid physical crossing bounds")
    if hashlib.sha256(opendrive_text.encode("utf-8")).hexdigest() != crossing["opendrive_sha256"]:
        raise ValueError("live OpenDRIVE differs from inspected source")
    if scene["ego_highway"] == scene["other_highway"]:
        raise ValueError("different highway identities required")
    if not scene.get("highway_identity_source") or not scene.get("public_access_source"):
        raise ValueError("highway identity and public access sources required")
    if crossing.get("kind") != "median_opening_roadway_crossing" or not crossing.get("id"):
        raise ValueError("identified roadway crossing at median opening required")
    if not scene.get("device_inventory_source"):
        raise ValueError("official device inventory source required")
    governing = scene["governing_signal"]
    if governing.get("kind") != "official_traffic_signal" or governing.get("readback_state") != "inoperative":
        raise ValueError("governing official signal must be read back inoperative")
    if set(governing.get("controlled_approach_road_ids", [])) != {
        scene["ego_approach_road_id"], scene["other_approach_road_id"]
    }:
        raise ValueError("governing signal does not bind both crossing approaches")
    directions = []
    for name in ("ego", "other"):
        route = scene[f"{name}_route_xy_m"]
        if len(route) < 3 or _point_inside(route[0], box) or _point_inside(route[-1], box):
            raise ValueError(f"{name} route must start and end outside crossing")
        if not any(_point_inside(p, box) for p in route[1:-1]):
            raise ValueError(f"{name} route does not cross identified intersection")
        directions.append((route[1][0]-route[0][0], route[1][1]-route[0][1]))
    norm = math.hypot(*directions[0]) * math.hypot(*directions[1])
    if norm == 0 or abs(sum(a*b for a, b in zip(*directions)) / norm) > 0.5:
        raise ValueError("approaches are not physically crossing")
    if scene["ego_approach_road_id"] == scene["other_approach_road_id"]:
        raise ValueError("distinct approach road IDs required")
    return crossing["id"]


def bind_native_map(world_map, scene, location_factory):
    """Verify mapped road IDs and junctions before spawning either actor."""
    validate_scene(scene, world_map.to_opendrive())
    bound = {}
    for name in ("ego", "other"):
        waypoints = []
        for x, y in scene[f"{name}_route_xy_m"]:
            waypoint = world_map.get_waypoint(location_factory(x, y), project_to_road=False)
            if waypoint is None or math.hypot(waypoint.transform.location.x-x, waypoint.transform.location.y-y) > 2:
                raise ValueError(f"{name} route is off mapped lane")
            waypoints.append(waypoint)
        if waypoints[0].road_id != scene[f"{name}_approach_road_id"]:
            raise ValueError(f"{name} approach road ID changed")
        if not any(w.is_junction for w in waypoints[1:-1]):
            raise ValueError(f"{name} mapped route lacks junction")
        bound[name] = waypoints
    return bound


def construct_native(world, scene, location_factory, blueprint_library, signal_readback):
    """Bind geometry and device, then spawn the two scoped vehicles lazily.

    A failed second spawn destroys the first actor. No simulator state is
    represented by scene flags alone; the signal callback reads live state.
    """
    bound = bind_native_map(world.get_map(), scene, location_factory)
    if signal_readback(scene["governing_signal"]) != "inoperative":
        raise ValueError("live governing signal is not inoperative")
    actors = {}
    try:
        for name in ("ego", "other"):
            blueprint_id = scene[f"{name}_blueprint"]
            if not blueprint_id.startswith("vehicle."):
                raise ValueError("conventional motor vehicle blueprint required")
            blueprint = blueprint_library.find(blueprint_id)
            actor = world.try_spawn_actor(blueprint, bound[name][0].transform)
            if actor is None:
                raise ValueError(f"{name} spawn failed")
            actors[name] = actor
        return actors, bound
    except Exception:
        for actor in actors.values():
            actor.destroy()
        raise


def requested_ego_control(ego_before_entry, other_inside, source_fresh):
    """Conservative request; measured behavior remains a separate observation."""
    if not source_fresh or (ego_before_entry and other_inside):
        return "brake"
    return "proceed"


def measure_saved(trace, scene, expected_frames=900):
    """Require complete original synchronized histories and report entry order."""
    if trace.get("case_id") != scene["case_id"] or trace.get("map_sha256") != scene["crossing"]["opendrive_sha256"]:
        raise ValueError("saved trace case or map source mismatch")
    frames = trace["frames"]
    if len(frames) != expected_frames:
        raise ValueError("incomplete original frame history")
    box = scene["crossing"]["bounds_xy_m"]
    entries = {"ego": None, "other": None}
    exits = {"ego": None, "other": None}
    prior = {"ego": False, "other": False}
    for index, frame in enumerate(frames):
        if frame.get("frame") != index or not math.isclose(frame.get("time_s", -1), index/20, abs_tol=1e-5):
            raise ValueError("original frame/time join is incomplete")
        if frame.get("signal_readback") != "inoperative":
            raise ValueError("governing signal did not remain inoperative")
        for name in ("ego", "other"):
            actor = frame[name]
            if actor.get("id") != trace["actor_ids"][name] or actor.get("road_id") != scene[f"{name}_approach_road_id"]:
                raise ValueError("actor or approach road source changed")
            vertices = actor.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) != 4 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in vertices):
                raise ValueError("original body footprint missing")
            inside = _rect_overlap(vertices, box)
            if index == 0 and inside:
                raise ValueError("entry was not observed from outside")
            if inside and not prior[name] and entries[name] is None:
                entries[name] = index
            if not inside and prior[name] and exits[name] is None:
                exits[name] = index
            prior[name] = inside
    if any(v is None for v in entries.values()) or any(v is None for v in exits.values()):
        raise ValueError("both original entry and exit events required")
    return {"case_id": scene["case_id"], "entry_frames": entries, "exit_frames": exits,
            "other_entered_before_ego": entries["other"] < entries["ego"],
            "ego_waited_until_other_exit": entries["ego"] >= exits["other"],
            "signal_inoperative_all_frames": True, "legal_judgment": "unresolved"}


def _rect_overlap(vertices, box):
    xs = [point[0] for point in vertices]
    ys = [point[1] for point in vertices]
    return max(xs) >= box[0] and min(xs) <= box[2] and max(ys) >= box[1] and min(ys) <= box[3]


def audit_comparison(first, second, first_scene, second_scene):
    fixed = ("crossing", "ego_highway", "other_highway", "ego_route_xy_m", "other_route_xy_m",
             "ego_approach_road_id", "other_approach_road_id", "governing_signal")
    for key in fixed:
        if first_scene[key] != second_scene[key]:
            raise ValueError(f"comparison fixed condition changed: {key}")
    if first["case_id"] == second["case_id"]:
        raise ValueError("comparison requires distinct exact cases")
    if not first["other_entered_before_ego"] or not second["other_entered_before_ego"]:
        raise ValueError("comparison lost earlier other entry")
    if first["ego_waited_until_other_exit"] == second["ego_waited_until_other_exit"]:
        raise ValueError("comparison lacks measured precedence-action difference")
    return {"fixed_conditions_checked": list(fixed), "difference": "measured ego crossing entry relative to other exit"}


def audit_saved_sources(root, manifest, scene):
    """Reject absent/stale original trace, map, device and four camera sources."""
    if manifest.get("case_id") != scene["case_id"] or manifest.get("frame_count") != 900:
        raise ValueError("source manifest case or frame count mismatch")
    required = ("native_trace", "opendrive", "device_inventory", "camera_front",
                "camera_rear", "camera_left", "camera_right")
    sources = manifest.get("sources", {})
    if set(sources) != set(required):
        raise ValueError("missing or extraneous original source")
    bound = {}
    root = Path(root).resolve()
    for name in required:
        ref = sources[name]
        path = (root / ref["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"missing original source: {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != ref.get("sha256"):
            raise ValueError(f"stale original source: {name}")
        bound[name] = digest
    if bound["opendrive"] != scene["crossing"]["opendrive_sha256"]:
        raise ValueError("original map differs from construction source")
    trace = json.loads((root / sources["native_trace"]["path"]).read_text())
    observation = measure_saved(trace, scene)
    return {"source_sha256": bound, "observations": observation,
            "physical_pixels_reviewed": False, "legal_judgment": "unresolved"}
