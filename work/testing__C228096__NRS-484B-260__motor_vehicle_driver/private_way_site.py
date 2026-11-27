"""Source-gated geometry for a private-way entrance to a public highway.

This module checks the authored site packet before any Native actor is created.
It does not decide whether a driver legally yielded or whether a CARLA run
realized the planned motion.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


REQUIRED_SOURCES = (
    "private_way_ownership",
    "private_way_access",
    "highway_status",
    "boundary_map",
    "connection_map",
    "native_opendrive_map",
)
SIDES = ("left", "right")


def _point(value, name):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(number) not in (int, float) or not math.isfinite(number)
        for number in value
    ):
        raise ValueError(name + " must be a finite XY point")
    return tuple(float(number) for number in value)


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _inside(point, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > point[1]) != (previous[1] > point[1]):
            x = (previous[0] - current[0]) * (point[1] - current[1]) / (
                previous[1] - current[1]
            ) + current[0]
            if point[0] < x:
                inside = not inside
        previous = current
    return inside


def _polygon(value, name):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(name + " needs at least three vertices")
    points = [_point(item, name) for item in value]
    if any(_distance(points[i], points[(i + 1) % len(points)]) < 0.05
           for i in range(len(points))):
        raise ValueError(name + " contains a degenerate edge")
    return points


def load_site(path: Path, expected_case: str) -> dict:
    """Verify original source hashes, legal site attributes and route geometry.

    The packet is a reviewed input to a prospective Native run. Source hashes
    protect its map and ownership records; booleans record reviewer conclusions,
    which a CPU fixture cannot establish independently.
    """
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    if site.get("format") != "worker-private-way-site-v1":
        raise ValueError("wrong private-way site packet format")
    if site.get("case_id") != expected_case:
        raise ValueError("site packet belongs to a different exact case")
    sources = site.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED_SOURCES):
        raise ValueError("all six original site sources are required")
    for name in REQUIRED_SOURCES:
        entry = sources[name]
        source_path = (path.parent / entry["path"]).resolve()
        if not source_path.is_relative_to(path.parent):
            raise ValueError("site source escaped its review directory: " + name)
        if not source_path.is_file():
            raise ValueError("missing original site source: " + name)
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != entry.get("sha256"):
            raise ValueError("original site source hash mismatch: " + name)
    assertions = site.get("reviewed_assertions", {})
    for key in ("private_ownership", "restricted_public_access",
                "destination_public_highway", "permitted_vehicular_use",
                "feasible_connection"):
        if assertions.get(key) is not True:
            raise ValueError("reviewed site assertion missing: " + key)
    origin = _polygon(site.get("private_way_polygon"), "private way")
    highway = _polygon(site.get("highway_polygon"), "highway")
    connection = _point(site.get("connection_xy"), "connection")
    if not _inside(connection, highway):
        raise ValueError("connection is outside the highway boundary")
    routes = site.get("routes")
    if not isinstance(routes, dict) or set(routes) != {"enter", "cross"}:
        raise ValueError("both entry and crossing routes are required")
    for maneuver, route in routes.items():
        if not isinstance(route, list) or len(route) < 3:
            raise ValueError(maneuver + " route has too few points")
        points = [_point(item, maneuver + " route") for item in route]
        if not _inside(points[0], origin):
            raise ValueError(maneuver + " route does not start in private way")
        if not any(_inside(item, highway) for item in points[1:]):
            raise ValueError(maneuver + " route never enters highway")
        if not any(_distance(item, connection) <= 1.0 for item in points):
            raise ValueError(maneuver + " route misses reviewed connection")
        if maneuver == "cross" and _inside(points[-1], highway):
            raise ValueError("crossing route never exits highway")
        if maneuver == "enter" and not _inside(points[-1], highway):
            raise ValueError("entry route does not continue on highway")
    approaches = site.get("approaches")
    if not isinstance(approaches, dict) or set(approaches) != set(SIDES):
        raise ValueError("both highway approach directions are required")
    axis = _point(site.get("highway_axis_xy"), "highway axis")
    axis_length = math.hypot(*axis)
    if axis_length < .1:
        raise ValueError("reviewed highway axis is degenerate")
    axis = [value / axis_length for value in axis]
    for side in SIDES:
        route = approaches[side]
        if not isinstance(route, list) or len(route) < 3:
            raise ValueError("missing highway approach path: " + side)
        points = [_point(item, side + " approach") for item in route]
        if not all(_inside(item, highway) for item in points):
            raise ValueError("approach leaves highway: " + side)
        distances = [_distance(point, connection) for point in points]
        nearest = min(range(len(points)), key=lambda i: distances[i])
        if nearest == 0 or nearest == len(points) - 1 or distances[nearest] > 1 or \
                distances[0] < distances[nearest] + 2 or \
                distances[-1] < distances[nearest] + 2:
            raise ValueError("approach is not directed through connection: " + side)
        initial_projection = sum((points[0][i] - connection[i]) * axis[i]
                                 for i in range(2))
        final_projection = sum((points[-1][i] - connection[i]) * axis[i]
                               for i in range(2))
        if ((side == "left" and not (initial_projection < -.5 and final_projection > .5)) or
                (side == "right" and not (initial_projection > .5 and final_projection < -.5))):
            raise ValueError("approach side is not directed through connection: " + side)
    return site


def assess_approaching(history: list[dict], required_sides: list[str]) -> dict:
    """Check source coverage and progression for every authored approach.

    Positive distance means an approaching vehicle is still short of the
    connection. The result is a motion observation, never a legal threshold.
    """
    if not history or not required_sides or set(required_sides) - set(SIDES):
        raise ValueError("nonempty left/right approach scope is required")
    observed = {side: [] for side in required_sides}
    for row in history:
        if type(row.get("frame")) is not int or type(row.get("time_s")) not in (int, float):
            raise ValueError("original frame and time are required")
        actors = row.get("highway_vehicles")
        if not isinstance(actors, list):
            raise ValueError("all highway vehicles must be inventoried each frame")
        seen = set()
        for actor in actors:
            identifier = actor.get("actor_id")
            side = actor.get("side")
            distance = actor.get("distance_to_connection_m")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise ValueError("highway actor identity missing or duplicated")
            seen.add(identifier)
            if side not in SIDES or type(distance) not in (int, float) or not math.isfinite(distance):
                raise ValueError("highway approach source is incomplete")
            if side in observed:
                observed[side].append((identifier, row["frame"], float(distance)))
    for side, rows in observed.items():
        if len(rows) < 2:
            raise ValueError("approaching vehicle source missing: " + side)
        by_actor = {}
        for identifier, frame, distance in rows:
            by_actor.setdefault(identifier, []).append((frame, distance))
        if not any(len(samples) >= 2 and
                   any(samples[i][1] > samples[i + 1][1] and samples[i][1] >= 0
                       for i in range(len(samples) - 1))
                   for samples in by_actor.values()):
            raise ValueError("no measured progression toward connection: " + side)
    return {"observed_sides": sorted(observed),
            "actor_ids": sorted({row[0] for rows in observed.values() for row in rows}),
            "legal_yield_judgment": "unresolved",
            "physical_acceptance_claimed": False}
