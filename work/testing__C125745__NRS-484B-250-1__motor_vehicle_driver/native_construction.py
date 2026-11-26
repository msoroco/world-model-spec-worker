"""Reviewed-source CARLA construction for the two exact C125745 cases.

The packet is an input to be reviewed against an original site. Diagnostic
packets may exercise this code, but cannot establish statutory applicability.
CARLA is deliberately imported only by a caller running on the Native host.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C125745__NRS-484B-250-1__motor_vehicle_driver"
CASES = ("precedence", "advance")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(packet_path, binding, label):
    _need(isinstance(binding, dict) and binding.get("citation"),
          "reviewed original citation required: " + label)
    name = binding.get("path")
    _need(isinstance(name, str) and name and not Path(name).is_absolute(),
          "reviewed original relative source required: " + label)
    root = packet_path.parent.resolve()
    path = packet_path.parent / name
    _need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
          and _sha(path) == binding.get("sha256"),
          "reviewed original bytes absent or stale: " + label)
    return path


def _route(scene, name):
    points = scene.get(name + "_route")
    _need(isinstance(points, list) and len(points) >= 2,
          "reviewed route missing: " + name)
    for point in points:
        _need(isinstance(point, list) and len(point) == 3 and
              all(type(value) in (int, float) and math.isfinite(value)
                  for value in point), "invalid reviewed route: " + name)
    _need(math.dist(points[0], points[1]) >= 1,
          "reviewed route has no approach heading: " + name)
    lane = scene.get(name + "_lane")
    _need(isinstance(lane, dict) and type(lane.get("road_id")) is int and
          type(lane.get("lane_id")) is int, "reviewed lane missing: " + name)
    return points


def reviewed_scene(packet_path, world, *, diagnostic=False):
    """Fail closed on map, source, fixed cell and statutory exception context."""
    path = Path(packet_path)
    _need(path.is_file() and not path.is_symlink(), "reviewed site packet missing")
    scene = json.loads(path.read_text(encoding="utf-8"))
    _need(scene.get("assignment_id") == ASSIGNMENT and
          scene.get("cell_id") == "C125745" and
          scene.get("control") == "stop_sign" and
          scene.get("maneuver") == "travel", "fixed assignment/cell differs")
    _need(scene.get("review_status") ==
          ("diagnostic_fixture" if diagnostic else "reviewed_original"),
          "reviewed original Native site packet required")
    _need(isinstance(scene.get("reviewer"), str) and scene["reviewer"] and
          isinstance(scene.get("map_source_citation"), str) and
          scene["map_source_citation"], "reviewed map citation required")
    road = world.get_map().to_opendrive().encode("utf-8")
    _need(hashlib.sha256(road).hexdigest() == scene.get("map_sha256"),
          "live OpenDRIVE differs from reviewed map")
    _source(path, scene.get("device_source"), "device")
    _source(path, scene.get("highway_source"), "highway")
    _need(scene.get("ego_highway") and scene.get("other_highway") and
          scene["ego_highway"] != scene["other_highway"] and
          scene.get("approach_relation") == "crossing" and
          scene.get("ego_side") in ("left", "right") and
          scene.get("other_side") in ("left", "right") and
          scene["ego_side"] != scene["other_side"],
          "different-highway crossing relation unreviewed")
    _need(scene.get("official_stop_sign_present") is True and
          type(scene.get("stop_sign_controls_intersection")) is bool and
          type(scene.get("subsection_4_reviewed")) is bool,
          "stop-sign governance or subsection-4 source review missing")
    _need(isinstance(scene.get("subsection_4_source_citation"), str) and
          scene["subsection_4_source_citation"],
          "subsection-4 statutory source citation missing")
    for key in ("crossing_id", "roadway_id", "map_source_citation",
                "highway_source_citation", "device_source_citation"):
        _need(isinstance(scene.get(key), str) and scene[key],
              "reviewed original crossing context missing: " + key)
    polygon = scene.get("intersection_polygon_xy_m")
    _need(isinstance(polygon, list) and len(polygon) >= 3 and
          all(isinstance(point, list) and len(point) == 2 and
              all(type(value) in (int, float) and math.isfinite(value)
                  for value in point) for point in polygon),
          "reviewed intersection polygon missing")
    for name in ("ego", "other"):
        _route(scene, name)
        _need(isinstance(scene.get(name + "_blueprint"), str) and
              scene[name + "_blueprint"], "reviewed blueprint missing: " + name)
    releases = scene.get("release_s")
    _need(isinstance(releases, dict) and set(releases) == set(CASES) and
          all(type(value) in (int, float) and math.isfinite(value) and value >= 0
              for value in releases.values()) and
          releases["precedence"] != releases["advance"],
          "two distinct reviewed ego response schedules required")
    other_release = scene.get("other_release_s")
    _need(type(other_release) in (int, float) and math.isfinite(other_release) and
          other_release >= 0, "reviewed other-vehicle release required")
    return scene


def _transform(carla, route):
    start, ahead = route[:2]
    yaw = math.degrees(math.atan2(ahead[1] - start[1], ahead[0] - start[0]))
    return carla.Transform(carla.Location(x=start[0], y=start[1], z=start[2]),
                           carla.Rotation(yaw=yaw))


def spawn_pair(world, carla, scene):
    """Spawn both reviewed approach directions; caller owns returned vehicles."""
    actors = []
    try:
        for name in ("ego", "other"):
            route = _route(scene, name)
            start = route[0]
            location = carla.Location(x=start[0], y=start[1], z=start[2])
            waypoint = world.get_map().get_waypoint(location, project_to_road=False)
            lane = scene[name + "_lane"]
            _need(waypoint is not None and
                  (waypoint.road_id, waypoint.lane_id) ==
                  (lane["road_id"], lane["lane_id"]),
                  "live approach lane differs: " + name)
            blueprint = world.get_blueprint_library().find(scene[name + "_blueprint"])
            actor = world.try_spawn_actor(blueprint, _transform(carla, route))
            if actor is None:
                raise RuntimeError("reviewed vehicle spawn failed: " + name)
            actors.append(actor)
        _need(actors[0].id != actors[1].id, "distinct Native actor IDs required")
        return tuple(actors)
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise
