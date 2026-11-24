"""Authored signed-intersection topology and strict Native readback.

Road geometry cannot establish legal through-highway status or proper sign
erection. Those facts require separate original-source review in each capture.
"""

import hashlib
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROAD = Path(__file__).resolve().parent / "native-map-plan/signed-intersection.xodr"
ROAD_OTHER_STOP = Path(__file__).resolve().parent / "native-map-plan/other-stop-intersection.xodr"
JUNCTION = 158209
EGO_APPROACH = 158208
OTHER_SOUTH = 158212
OTHER_NORTH = 158214


def _driving_lanes(road):
    return {int(lane.attrib["id"]) for lane in road.findall("./lanes/laneSection/left/lane")
            + road.findall("./lanes/laneSection/right/lane")
            if lane.attrib.get("type") == "driving"}


def validate_authored_site(path=ROAD, *, other_stop=False):
    path = Path(path)
    root = ET.parse(path).getroot()
    roads = {int(road.attrib["id"]): road for road in root.findall("road")}
    if root.tag != "OpenDRIVE" or set(roads) != {158208, 158210, 158211, 158212, 158213, 158214}:
        raise ValueError("Authored signed-intersection roads differ")
    if _driving_lanes(roads[EGO_APPROACH]) != {-1}:
        raise ValueError("Signed ego approach is not one-way")
    for road_id in (OTHER_SOUTH, 158213, OTHER_NORTH):
        if _driving_lanes(roads[road_id]) != {-1, 1}:
            raise ValueError("Cross street is not two-way")
    if any(roads[road_id].attrib.get("junction") != str(JUNCTION) for road_id in (158210, 158213)):
        raise ValueError("Missing crossing junction membership")
    junction = root.find(f"./junction[@id='{JUNCTION}']")
    if junction is None:
        raise ValueError("Missing authored signed junction")
    links = {(int(link.attrib["incomingRoad"]), int(link.attrib["connectingRoad"]),
              tuple((int(lane.attrib["from"]), int(lane.attrib["to"])) for lane in link.findall("laneLink")))
             for link in junction.findall("connection")}
    if links != {(158208, 158210, ((-1, -1),)),
                 (158212, 158213, ((-1, -1),)),
                 (158214, 158213, ((1, 1),))}:
        raise ValueError("Signed-junction route connectivity differs")
    signals = roads[EGO_APPROACH].findall("./signals/signal")
    other_signals = roads[OTHER_SOUTH].findall("./signals/signal")
    if (len(signals) != 1 or signals[0].attrib.get("type") != "205"
            or len(other_signals) != int(other_stop)
            or len(root.findall(".//signal")) != 1 + int(other_stop)):
        raise ValueError("Expected authored yield sign and selected other stop sign")
    validity = signals[0].find("validity")
    if (signals[0].attrib.get("orientation") != "+"
            or not math.isclose(float(signals[0].attrib["s"]), 60.0)
            or validity is None or validity.attrib.get("fromLane") != "-1"
            or validity.attrib.get("toLane") != "-1"):
        raise ValueError("Authored yield sign does not govern ego lane")
    if other_stop:
        stop = other_signals[0]
        other_validity = stop.find("validity")
        if (stop.attrib.get("type") != "206" or stop.attrib.get("orientation") != "+"
                or not math.isclose(float(stop.attrib["s"]), 60.0)
                or other_validity is None or other_validity.attrib.get("fromLane") != "-1"
                or other_validity.attrib.get("toLane") != "-1"):
            raise ValueError("Other stop sign does not govern selected entrance")
    if root.findall(".//object"):
        raise ValueError("Unexpected authored road object")
    return {"road_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "intersection_id": JUNCTION, "ego_approach_road_id": EGO_APPROACH,
            "other_approach_road_ids": [OTHER_SOUTH, OTHER_NORTH],
            "yield_signal_id": signals[0].attrib["id"],
            "other_stop_signal_id": other_signals[0].attrib["id"] if other_stop else None,
            "non_through_highway_judgment": "unresolved",
            "proper_sign_judgment": "unresolved"}


def validate_native_site(world, *, other_stop=False, location_factory=None):
    if location_factory is None:
        import carla
        location_factory = carla.Location
    road_map = world.get_map()
    probes = ((-20, 1.8, 158208, -1, False),
              (0, 1.8, 158210, -1, True),
              (1.8, 20, 158212, -1, False),
              (1.8, 0, 158213, -1, True),
              (-1.8, -20, 158214, 1, False))
    for x, y, road_id, lane_id, junction in probes:
        waypoint = road_map.get_waypoint(location_factory(x=x, y=y, z=.25), project_to_road=False)
        if (waypoint is None or waypoint.road_id != road_id or waypoint.lane_id != lane_id
                or bool(waypoint.is_junction) != junction):
            raise ValueError("Native signed-junction road/lane probe differs")
    approach = location_factory(x=-20, y=1.8, z=.25)
    signs = [actor for actor in world.get_actors().filter("traffic.yield*")
             if actor.trigger_volume.contains(approach, actor.get_transform())]
    if len(signs) != 1:
        raise ValueError("Expected one Native yield sign governing ego approach")
    other_sign_id = None
    if other_stop:
        south = location_factory(x=1.8, y=20, z=.25)
        stops = [actor for actor in world.get_actors().filter("traffic.stop*")
                 if actor.trigger_volume.contains(south, actor.get_transform())]
        if len(stops) != 1:
            raise ValueError("Expected one Native stop sign governing other entrance")
        other_sign_id = stops[0].id
    return {"native_map_id": road_map.name, "intersection_id": JUNCTION,
            "ego_approach_road_id": EGO_APPROACH,
            "other_approach_road_ids": [OTHER_SOUTH, OTHER_NORTH],
            "native_yield_sign_id": signs[0].id,
            "native_other_stop_sign_id": other_sign_id,
            "non_through_highway_judgment": "unresolved",
            "proper_sign_judgment": "unresolved"}


def load_native_site(client, *, other_stop=False):
    path = ROAD_OTHER_STOP if other_stop else ROAD
    validate_authored_site(path, other_stop=other_stop)
    world = client.generate_opendrive_world(path.read_text())
    return world, validate_native_site(world, other_stop=other_stop)
