"""Independent source/controlled-pair audit for the C110454 CPU proposal."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROAD = HERE / "native/road.xodr"
ROUTES = {name: HERE / "native/routes" / (name + ".json")
          for name in ("reference", "contrast")}
BOUNDARY_M = 30.48


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def left_interval(points):
    # Conservative fixed 2.6 x 1.1 m prospective body in a straight approach.
    selected = [x for x, y in points if y - 1.1 > 0]
    if not selected:
        raise ValueError("No full-body left-of-center approach")
    return min(selected), max(selected)


def audit():
    xml = ET.parse(ROAD).getroot()
    roads = {int(item.attrib["id"]): item for item in xml.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise ValueError("Intersection road identity differs")
    links = {(int(c.attrib["incomingRoad"]), int(c.attrib["connectingRoad"]))
             for c in xml.findall("junction/connection")}
    if links != {(1, 13), (3, 14)}:
        raise ValueError("Two-way junction connection differs")
    for ident in roads:
        section = roads[ident].find("lanes/laneSection")
        if {int(l.attrib["id"]) for l in section.findall("./*/lane")} != {-1, 0, 1}:
            raise ValueError("Two-way driving lane IDs differ")
    bay = roads[2].find("objects/object[@type='parkingSpace']")
    if bay is None or float(bay.attrib["length"]) != 27:
        raise ValueError("Authored parking surface differs")
    data = {name: json.loads(path.read_text()) for name, path in ROUTES.items()}
    for name, points in data.items():
        if len(points) != 901 or any(len(p) != 2 for p in points):
            raise ValueError("Route sample count differs: " + name)
        if max(math.dist(a, b) for a, b in zip(points, points[1:])) >= .15:
            raise ValueError("Route discontinuity: " + name)
        if points[0] != [-70.0, -1.75] or points[-1] != [20.0, -5.25]:
            raise ValueError("Held route endpoints differ")
        if any(a != b for a, b in zip(points, data["reference"])
               if a[0] < -60 or a[0] > -8):
            raise ValueError("Noncomparison route segment differs")
    intervals = {name: left_interval(points) for name, points in data.items()}
    if intervals["reference"][1] + 2.6 >= -7 - BOUNDARY_M:
        raise ValueError("Reference body enters 100-foot zone")
    if intervals["contrast"][0] + 2.6 < -7 - BOUNDARY_M:
        raise ValueError("Contrast left-body interval does not lie inside 100-foot zone")
    if abs((intervals["contrast"][0] - intervals["reference"][0]) - 32) > .2:
        raise ValueError("Excursion translation differs")
    output = {"passed": True, "scope": "authored OpenDRIVE and prospective sampled body",
              "road_sha256": sha(ROAD),
              "route_sha256": {name: sha(path) for name, path in ROUTES.items()},
              "full_body_left_x_intervals_m": intervals,
              "statutory_approach_boundary_m": BOUNDARY_M,
              "same_parking_endpoint": True, "native_observed": False,
              "legal_verdict_claimed": False}
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    audit()
