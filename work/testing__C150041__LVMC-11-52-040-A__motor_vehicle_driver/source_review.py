"""Retained-source preflight for the C150041 parking geometry context."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parking_measurement import inside, unit, vector


REQUIRED = ("roadway", "one_way_direction", "activity", "chapter_exceptions")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retained_source(root, item, name):
    if not isinstance(item, dict):
        raise ValueError(name + " source descriptor missing")
    rel = item.get("path")
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError(name + " source path must be local")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(name + " original source missing")
    if item.get("sha256") != sha(path):
        raise ValueError(name + " original source hash changed")
    if not item.get("reviewer") or not item.get("citation"):
        raise ValueError(name + " reviewer and citation required")
    return item["sha256"]


def validate(packet_path, *, source_root, require_reviewed=True):
    packet_path = Path(packet_path)
    root = Path(source_root)
    packet = json.loads(packet_path.read_text())
    if packet.get("assignment_id") != "testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver":
        raise ValueError("parking source packet assignment differs")
    if require_reviewed and packet.get("review_status") != "reviewed":
        raise ValueError("parking site sources have not been reviewed")
    sources = packet.get("sources", {})
    if set(sources) != set(REQUIRED):
        raise ValueError("roadway, direction, activity and Chapter sources required")
    hashes = {name: retained_source(root, sources[name], name) for name in REQUIRED}
    context = packet.get("context", {})
    if (context.get("roadway_kind") != "one_way_road" or
            context.get("responsible_person_role") != "motor_vehicle_driver" or
            context.get("activity") not in ("stand", "park") or
            context.get("chapter_exception_review") not in ("no_applicable_exception_found", "unresolved")):
        raise ValueError("parking roadway, person, activity or Chapter context incomplete")
    edge = context.get("road_edge_xy_m")
    polygon = context.get("roadway_polygon_xy_m")
    lawful = unit(context.get("lawful_travel_xy", []))
    if (not isinstance(edge, list) or len(edge) < 2 or
            not isinstance(polygon, list) or len(polygon) < 3):
        raise ValueError("parking roadway geometry missing")
    points = edge + polygon
    if any(len(point) != 2 or any(not isinstance(value, (int, float)) or
                                  not math.isfinite(value) for value in point)
           for point in points):
        raise ValueError("parking roadway geometry must be finite XY")
    for start, end in zip(edge, edge[1:]):
        direction = unit(vector(start, end))
        if abs(sum(direction[i] * lawful[i] for i in (0, 1))) < .9:
            raise ValueError("road edge and reviewed lawful direction conflict")
        middle = tuple((start[i] + end[i]) / 2 for i in (0, 1))
        normal = (-direction[1], direction[0])
        sided = [inside(tuple(middle[i] + sign * .1 * normal[i] for i in (0, 1)), polygon)
                 for sign in (-1, 1)]
        if sided.count(True) != 1:
            raise ValueError("road edge does not bound one side of reviewed roadway")
    return {"road_edge_xy_m": edge, "roadway_polygon_xy_m": polygon,
            "lawful_travel_xy": lawful,
            "road_edge_source": hashes["roadway"],
            "roadway_source": hashes["roadway"],
            "lawful_direction_source": hashes["one_way_direction"],
            "activity_source": hashes["activity"],
            "chapter_exception_source": hashes["chapter_exceptions"],
            "reviewed_packet_sha256": sha(packet_path),
            "activity": context["activity"],
            "chapter_exception_review": context["chapter_exception_review"],
            "legal_judgment": "unresolved"}
