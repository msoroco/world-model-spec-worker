"""Native sidewalk bypass construction for C109128.

All coordinates are engineering requests. Native map, actor and pose readbacks
are retained separately; no request is treated as an observed legal fact.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET

RATE_HZ = 20
FRAMES = 600
SIDEWALK = (-6.0, -4.0)
SHOULDER = (-4.0, -3.5)
ROADWAY = (-3.5, 0.0)
OBSTRUCTION_X = (20.0, 30.0)
OBSTRUCTION_Y = (-5.6, -4.4)
START_X = 5.0
SPEED_MPS = 1.5
SIDEWALK_CENTER_Y = -5.0
BYPASS_Y = {"condition_a": -3.82, "condition_b": -3.62}
ALTERNATIVE_Y = {"direction_east": -3.82, "direction_west": -3.82,
                 "bike_passable": -4.8, "bike_impassable": -4.1}
CONDITIONS = tuple(BYPASS_Y) + tuple(ALTERNATIVE_Y)
CAMERAS = (
    ("overview", 1920, 1080, 27.0, -14.0, 25.0, -55.0),
    ("approach", 1280, 720, 12.0, -12.0, 7.0, -20.0),
    ("reference_corner", 1280, 720, 38.0, -13.0, 7.0, -20.0),
    ("driver_reference", 1280, 720, 15.0, 0.0, 2.5, -12.0),
)


def geometry(condition):
    if condition not in CONDITIONS:
        raise ValueError("unknown exact sidewalk alternative")
    bicycle = condition.startswith("bike_")
    return {"sidewalk": (-7.0, -5.0) if bicycle else SIDEWALK,
            "sidewalk_center_y": -6.0 if bicycle else SIDEWALK_CENTER_Y,
            "shoulder": (-5.0, -4.5) if bicycle else SHOULDER,
            "bicycle": (-4.5, -3.5) if bicycle else None,
            "roadway": ROADWAY,
            "road_direction": "east",
            "walking_direction": "west" if condition == "direction_west" else "east",
            "intervening_area_requested_impassable": condition == "bike_impassable"}


def open_drive(condition="condition_a") -> str:
    layout = geometry(condition)
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C109128-sidewalk-bypass", version="1", date="2026-11-25",
                  north="30", south="-30", east="65", west="-15",
                  vendor="full-train-worker")
    roads = ((1, -80, 0, 0, 70, -1), (2, 0, 0, 0, 70, -1),
             (3, -5, -80, math.pi / 2, 70, -1),
             (4, -5, 0, math.pi / 2, 70, -1),
             (13, -10, 0, 0, 10, 100),
             (14, -5, -10, math.pi / 2, 10, 100))
    for ident, x, y, heading, length, junction in roads:
        road = ET.SubElement(root, "road", id=str(ident),
                             name=f"c109128-road-{ident}", length=str(length),
                             junction=str(junction))
        link = ET.SubElement(road, "link")
        if ident in (1, 3):
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif ident in (2, 4):
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        else:
            before, after = (1, 2) if ident == 13 else (3, 4)
            ET.SubElement(link, "predecessor", elementType="road",
                          elementId=str(before), contactPoint="end")
            ET.SubElement(link, "successor", elementType="road",
                          elementId=str(after), contactPoint="start")
        segment = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                                s="0", x=str(x), y=str(y), hdg=str(heading),
                                length=str(length))
        ET.SubElement(segment, "line")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        ET.SubElement(section, "left")
        center = ET.SubElement(section, "center")
        ET.SubElement(center, "lane", id="0", type="none", level="false")
        right = ET.SubElement(section, "right")
        parts = (((-1, "driving", 3.5), (-2, "biking", 1.0),
                  (-3, "shoulder", .5), (-4, "sidewalk", 2.0)) if
                 layout["bicycle"] else
                 ((-1, "driving", 3.5), (-2, "shoulder", .5),
                  (-3, "sidewalk", 2.0))) if ident == 2 else ((-1, "driving", 3.5),)
        for lane_id, kind, width in parts:
            lane = ET.SubElement(right, "lane", id=str(lane_id), type=kind,
                                 level="false")
            if ident in (13, 14):
                lane_link = ET.SubElement(lane, "link")
                ET.SubElement(lane_link, "predecessor", id=str(lane_id))
                ET.SubElement(lane_link, "successor", id=str(lane_id))
            ET.SubElement(lane, "width", sOffset="0", a=str(width), b="0",
                          c="0", d="0")
            ET.SubElement(lane, "roadMark", sOffset="0", type="solid",
                          color="white", width="0.1")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100", name="c109128-four-way")
    for index, incoming, connector in ((0, 1, 13), (1, 3, 14)):
        connection = ET.SubElement(junction, "connection", id=str(index),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connector), contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def _target_y(road_y: float, frame: int, sidewalk_center_y=SIDEWALK_CENTER_Y) -> float:
    if frame < 170:
        return sidewalk_center_y
    if frame < 200:
        return sidewalk_center_y + (road_y - sidewalk_center_y) * (frame - 170) / 30
    if frame < 370:
        return road_y
    if frame < 400:
        return road_y + (sidewalk_center_y - road_y) * (frame - 370) / 30
    return sidewalk_center_y


def request(condition: str, frame: int, *, lateral_shift_m: float = 0.0) -> dict:
    if condition not in CONDITIONS or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("exact bypass condition/frame required")
    if not -0.2 <= lateral_shift_m <= 0.2:
        raise ValueError("lateral engineering shift outside fallback envelope")
    layout = geometry(condition)
    direction = -1 if layout["walking_direction"] == "west" else 1
    x = (45.0 if direction == -1 else START_X) + direction * SPEED_MPS * frame / RATE_HZ
    road_y = (BYPASS_Y | ALTERNATIVE_Y)[condition] + lateral_shift_m
    y = _target_y(road_y, frame, layout["sidewalk_center_y"])
    previous_y = y if frame == 0 else _target_y(road_y, frame - 1, layout["sidewalk_center_y"])
    vx, vy = direction * SPEED_MPS, (y - previous_y) * RATE_HZ
    norm = math.hypot(vx, vy)
    return {"frame": frame, "time_s": frame / RATE_HZ,
            "target_xy_m": [round(x, 6), round(y, 6)],
            "walker_direction_xyz": [vx / norm, vy / norm, 0.0],
            "walker_speed_mps": norm,
            "requested_sidewalk_exit": 170 <= frame < 400,
            "source_kind": "authored_native_request", "native_pose_observed": False}


def apply_control(walker, carla, condition: str, frame: int,
                  lateral_shift_m: float = 0.0) -> dict:
    row = request(condition, frame, lateral_shift_m=lateral_shift_m)
    walker.apply_control(carla.WalkerControl(
        carla.Vector3D(*row["walker_direction_xyz"]), row["walker_speed_mps"], False))
    return row


def survey(world, carla, condition="condition_a") -> dict:
    mapping = world.get_map()
    layout = geometry(condition)
    samples = {}
    lane_plan = [("roadway", -1.75, carla.LaneType.Driving, -1)]
    if layout["bicycle"]:
        lane_plan.append(("bicycle", -4.0, carla.LaneType.Biking, -2))
        lane_plan.append(("shoulder", -4.75, carla.LaneType.Shoulder, -3))
        lane_plan.append(("sidewalk", -6.0, carla.LaneType.Sidewalk, -4))
    else:
        lane_plan.extend((("shoulder", -3.75, carla.LaneType.Shoulder, -2),
                          ("sidewalk", -5.0, carla.LaneType.Sidewalk, -3)))
    for name, y, kind, lane_id in lane_plan:
        rows = []
        for x in (5.0, 19.0, 25.0, 31.0, 50.0):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=.4),
                                      project_to_road=True, lane_type=kind)
            if wp is None or wp.road_id != 2 or wp.lane_id != lane_id:
                raise ValueError("Native adjacent lane readback missing: " + name)
            observed = wp.transform.location
            if abs(observed.x - x) > 1.0 or abs(observed.y - y) > 1.0:
                raise ValueError("Native adjacent lane geometry differs: " + name)
            rows.append({"x_requested_m": x, "native_xyz_m":
                         [observed.x, observed.y, observed.z], "road_id": wp.road_id,
                         "lane_id": wp.lane_id, "lane_type": str(wp.lane_type)})
        samples[name] = rows
    return {"source_kind": "original_native_map_readback", "lanes": samples,
            "sidewalk_y_m": list(layout["sidewalk"]), "shoulder_y_m": list(layout["shoulder"]),
            "roadway_y_m": list(ROADWAY), "bike_lane_designation": "native_biking_lane" if layout["bicycle"] else "absent",
            "bicycle_y_m": list(layout["bicycle"]) if layout["bicycle"] else None,
            "road_direction": layout["road_direction"],
            "walking_direction_requested": layout["walking_direction"],
            "intervening_area_requested_impassable": layout["intervening_area_requested_impassable"],
            "legal_highway_status_review_pending": True}


def spawn_obstruction(world, carla, condition="condition_a", *, raise_z_m: float = 0.0) -> list:
    """Place a row of actual collision-enabled Native actors across sidewalk.

    A static prop blueprint may vary by CARLA build. Fail if none exists or if
    physical bounding boxes do not cover the intended sidewalk strip.
    """
    if not 0 <= raise_z_m <= .2:
        raise ValueError("obstruction fallback elevation outside envelope")
    library = world.get_blueprint_library()
    names = ("static.prop.streetbarrier", "static.prop.constructioncone",
             "static.prop.trafficcone01")
    available = {bp.id: bp for bp in library.filter("static.prop.*")}
    blueprint = next((available[name] for name in names if name in available), None)
    if blueprint is None:
        raise ValueError("Native collision prop blueprint for sidewalk obstruction absent")
    owned = []
    try:
        layout = geometry(condition)
        for x in (21.0, 23.0, 25.0, 27.0, 29.0):
            for y in ((-6.4, -5.8) if layout["bicycle"] else (-5.4, -4.8)):
                actor = world.try_spawn_actor(blueprint, carla.Transform(
                    carla.Location(x=x, y=y, z=.1 + raise_z_m), carla.Rotation()))
                if actor is None:
                    raise ValueError("Native sidewalk obstruction spawn failed")
                owned.append(actor)
        for actor in owned:
            pose = actor.get_transform().location
            if not (20 <= pose.x <= 30 and layout["sidewalk"][0] <= pose.y <= layout["sidewalk"][1]):
                raise ValueError("Native obstruction readback outside sidewalk")
            box = actor.bounding_box
            if box.extent.x <= 0 or box.extent.y <= 0 or box.extent.z <= 0:
                raise ValueError("Native obstruction bounding box absent")
        if layout["intervening_area_requested_impassable"]:
            for x in (21.0, 23.0, 25.0, 27.0, 29.0):
                actor = world.try_spawn_actor(blueprint, carla.Transform(
                    carla.Location(x=x, y=-4.75, z=.1 + raise_z_m), carla.Rotation()))
                if actor is None:
                    raise ValueError("Native intervening shoulder obstruction spawn failed")
                owned.append(actor)
        return owned
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise


def check(condition="condition_a") -> dict:
    layout = geometry(condition)
    root = ET.fromstring(open_drive(condition))
    roads = {int(road.attrib["id"]): road for road in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14} or len(root.findall("junction/connection")) != 2:
        raise ValueError("authored four-way junction missing")
    road = roads[2]
    lanes = road.findall("lanes/laneSection/right/lane")
    inventory = [(int(lane.attrib["id"]), lane.attrib["type"],
                  float(lane.find("width").attrib["a"])) for lane in lanes]
    expected = ([(-1, "driving", 3.5), (-2, "biking", 1.0),
                 (-3, "shoulder", .5), (-4, "sidewalk", 2.0)] if layout["bicycle"] else
                [(-1, "driving", 3.5), (-2, "shoulder", .5), (-3, "sidewalk", 2.0)])
    if road.attrib["length"] != "70" or inventory != expected:
        raise ValueError("authored Native highway/sidewalk geometry changed")
    if len(CAMERAS) != 4 or len({camera[0] for camera in CAMERAS}) != 4:
        raise ValueError("four independent cameras required")
    for candidate in CONDITIONS:
        candidate_layout = geometry(candidate)
        start = request(candidate, 0)["target_xy_m"]
        exit_start = request(candidate, 170)["target_xy_m"]
        bypass = request(candidate, 250)["target_xy_m"]
        return_end = request(candidate, 400)["target_xy_m"]
        reverse = candidate == "direction_west"
        if (start[1] != candidate_layout["sidewalk_center_y"] or
                (exit_start[0] <= OBSTRUCTION_X[1] if reverse else exit_start[0] >= OBSTRUCTION_X[0]) or
                bypass[1] <= candidate_layout["sidewalk"][1] or
                (return_end[0] >= OBSTRUCTION_X[0] if reverse else return_end[0] <= OBSTRUCTION_X[1]) or
                return_end[1] != candidate_layout["sidewalk_center_y"]):
            raise ValueError("obstruction bypass or return geometry changed")
    return {"passed": True, "frames": FRAMES, "rate_hz": RATE_HZ,
            "lane_inventory": inventory, "camera_names": [c[0] for c in CAMERAS],
            "obstruction_actor_count_requested": 10,
            "native_executed": False, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
