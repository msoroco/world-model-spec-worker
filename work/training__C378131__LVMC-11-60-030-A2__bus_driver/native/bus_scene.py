"""Authored bus loading requests. Legal designation remains a source question."""

import xml.etree.ElementTree as ET

ZONE_KINDS = ("bus_stop", "bus_stand", "passenger_loading_zone",
              "route_origin", "route_destination", "other_street")
CAMERAS = ("front", "rear", "left", "right")
RATE_HZ = 20
FRAMES = 600


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C378131-bus-street",
                  version="1", north="25", south="-25", east="90", west="-90",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="378131", name="bus_route_street",
                         length="160", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-80", y="0", hdg="0", length="160")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, lane_id, kind in (("left", 1, "none"), ("center", 0, "none"),
                                ("right", -1, "driving")):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(lane_id),
                             type=kind, level="false")
        if lane_id:
            ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
    objects = ET.SubElement(road, "objects")
    ET.SubElement(objects, "object", id="loading-place-378131", s="55", t="-3.7",
                  name="bus-loading-place-marker", type="curb", orientation="none",
                  zOffset="0", length="24", width="0.2", height="0.15", hdg="0",
                  pitch="0", roll="0")
    return ET.tostring(root, encoding="unicode")


def request(zone_kind, *, vehicle_class="route_bus_non_tour", emergency=False):
    if zone_kind not in ZONE_KINDS:
        raise ValueError("unknown loading location kind")
    if vehicle_class not in ("route_bus_non_tour", "tour_bus"):
        raise ValueError("unknown bus class")
    return {
        "format": "worker-authored-bus-loading-request",
        "road_opendrive": road_xml(), "zone_kind": zone_kind,
        "zone_id": "loading-place-378131", "route_id": "R-378131",
        "vehicle_class_requested": vehicle_class,
        "emergency_requested": emergency,
        "ego": {"blueprint": "vehicle.mitsubishi.fusorosa", "start_xyz": [-35, -1.75, .5],
                "heading_deg": 0, "target_speed_mps": 5.0},
        "passenger": {"blueprint_filter": "walker.pedestrian.*",
                      "start_xyz": [-10, -5.5, .5], "target_door_xyz": [-12, -3.2, .5]},
        "controller": {"halt_request_frame": 90, "door_open_request_frame": 140,
                       "passenger_walk_request_frame": 170, "door_close_request_frame": 420,
                       "resume_request_frame": 480},
        "cameras": [
            {"name": "front", "xyz": [-2, -11, 8], "pitch": -24, "yaw": 160,
             "size": [1920, 1080]},
            {"name": "rear", "xyz": [-12, -17, 18], "pitch": -42, "yaw": 40,
             "size": [1280, 720]},
            {"name": "left", "xyz": [-12, -9, 6], "pitch": -24, "yaw": 70,
             "size": [1280, 720]},
            {"name": "right", "xyz": [1, 0, 2], "pitch": -8, "yaw": 0,
             "attach_to_ego": True, "size": [1280, 720]}],
        "rate_hz": RATE_HZ, "planned_frames": FRAMES, "duration_s": 30,
        "designation_authority_confirmed": False,
        "actual_loading_confirmed": False, "physical_acceptance_claimed": False,
    }


def validate(scene):
    root = ET.fromstring(scene["road_opendrive"])
    roads = root.findall("road")
    if root.tag != "OpenDRIVE" or len(roads) != 1 or roads[0].get("id") != "378131":
        raise ValueError("bus street geometry missing")
    marker = roads[0].find("objects/object")
    if marker is None or marker.get("id") != scene["zone_id"]:
        raise ValueError("loading-place marker missing")
    if scene["zone_kind"] not in ZONE_KINDS or not scene["route_id"]:
        raise ValueError("route or loading location missing")
    if {item["name"] for item in scene["cameras"]} != set(CAMERAS):
        raise ValueError("four source cameras missing")
    if any(tuple(item["size"]) != ((1920, 1080) if item["name"] == "front" else
                                    (1280, 720)) for item in scene["cameras"]):
        raise ValueError("capture profile differs")
    if (scene["rate_hz"], scene["planned_frames"], scene["duration_s"]) != (20, 600, 30):
        raise ValueError("20 Hz duration differs")
    if any(scene[key] for key in ("designation_authority_confirmed",
                                 "actual_loading_confirmed", "physical_acceptance_claimed")):
        raise ValueError("authored request claims observation")
    return {"zone_kind": scene["zone_kind"], "camera_count": 4,
            "planned_frames": FRAMES, "original_native_observed": False}
