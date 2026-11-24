"""Authored intersection parking probes. CPU geometry is not Native observation."""
from __future__ import annotations
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
INTERSECTION = (-7.0, -7.0, 7.0, 7.0)
BODY_LENGTH_M = 5.2
BODY_WIDTH_M = 2.2
STOP_X = {"probe_a": -13.0, "probe_b": 0.0}
START_X = -50.0
STEP_M = 0.1


def road_xml() -> str:
    return (HERE / "road.xodr").read_text()


def body(x: float, y: float = -1.75) -> list[list[float]]:
    return [[round(x + dx, 5), round(y + dy, 5)] for dx, dy in
            ((-2.6, -1.1), (-2.6, 1.1), (2.6, 1.1), (2.6, -1.1))]


def route(suffix: str) -> list[list[float]]:
    if suffix not in STOP_X:
        raise ValueError("Unknown parking probe")
    n = round((STOP_X[suffix] - START_X) / STEP_M)
    return [[round(START_X + i * STEP_M, 5), -1.75] for i in range(n + 1)]


def overlap_area_xy(vertices: list[list[float]]) -> float:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    x = max(0.0, min(max(xs), INTERSECTION[2]) - max(min(xs), INTERSECTION[0]))
    y = max(0.0, min(max(ys), INTERSECTION[3]) - max(min(ys), INTERSECTION[1]))
    return x * y


def check() -> dict:
    root = ET.fromstring(road_xml())
    roads = {int(r.attrib["id"]): r for r in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14} or len(root.findall("junction/connection")) != 2:
        raise ValueError("Authored two-way intersection topology differs")
    if not all(roads[1].find("lanes/laneSection/right/lane[@id='-1']") is not None
               for _ in (0,)):
        raise ValueError("Inbound driving lane missing")
    out = {}
    for suffix in STOP_X:
        points = route(suffix)
        if any(abs(math.dist(a, b) - STEP_M) > 1e-8 for a, b in zip(points, points[1:])):
            raise ValueError("Route step discontinuity")
        footprint = body(*points[-1])
        overlap = overlap_area_xy(footprint)
        if suffix == "probe_a" and overlap != 0:
            raise ValueError("Outside probe enters intersection")
        if suffix == "probe_b" and overlap < 10:
            raise ValueError("Inside probe lacks a full-body overlap margin")
        out[suffix] = {"stop_center_xy_m": points[-1], "stop_body_xy_m": footprint,
                       "authored_intersection_overlap_m2": round(overlap, 5),
                       "route_points": len(points)}
    return {"passed": True, "law_id": "NRS-484B-450-1c", "cell_id": "C110454",
            "comparison_variable": "intersection_parking_footprint",
            "scope": "authored OpenDRIVE and prospective 5.2 x 2.2 m body only",
            "native_or_legal_outcome_claimed": False, "probes": out}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
