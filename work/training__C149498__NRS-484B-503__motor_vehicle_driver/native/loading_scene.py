"""Source-shaped exact passenger curb loading scene requests.

These authored inputs require Native map and actor readback before use. A sign
in an authored map does not establish regulatory authority or expeditiousness.
"""

import xml.etree.ElementTree as ET

CASES = {"condition_a": True, "condition_b": False}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
RATE_HZ = 20
FRAMES = 600


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C149498-passenger-curb",
                  version="1", north="25", south="-25", east="90", west="-90",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="149498", name="one_way_loading_road",
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
    ET.SubElement(objects, "object", id="passenger-zone-curb-149498", s="55", t="-3.7",
                  name="marked_passenger_curb_loading_zone", type="curb", orientation="none",
                  zOffset="0", length="24", width="0.2", height="0.15", hdg="0",
                  pitch="0", roll="0")
    signals = ET.SubElement(road, "signals")
    ET.SubElement(signals, "signal", id="passenger-loading-sign-149498", s="55",
                  t="-4.1", name="PASSENGER LOADING 08:00-18:00 America/Los_Angeles",
                  dynamic="no", orientation="+", zOffset="0", country="US",
                  type="passenger-loading", subtype="0", value="0", unit="",
                  height="0.8", width="0.8")
    return ET.tostring(root, encoding="unicode")


def request(slug):
    if slug not in CASES:
        raise ValueError("unknown exact loading case")
    return {
        "format": "worker-authored-passenger-curb-request",
        "case": slug, "road_opendrive": road_xml(),
        "zone": {"kind": "passenger_curb_loading", "object_id": "passenger-zone-curb-149498",
                 "sign_id": "passenger-loading-sign-149498", "curb_start_x_m": -25,
                 "curb_end_x_m": -1, "time_zone": "America/Los_Angeles",
                 "hours_start": "08:00", "hours_end": "18:00",
                 "civil_timestamp_start": "2026-11-23T10:00:00-08:00",
                 "legal_authority": "unverified_original_source"},
        "ego": {"blueprint": "vehicle.tesla.model3", "start_xyz": [-45, -1.75, 0.5],
                "heading_deg": 0, "target_halt_center_x_m": -12, "target_speed_mps": 3.0},
        "passenger": {"blueprint_filter": "walker.pedestrian.*",
                      "start_xyz": [-10, -5.5, 0.5],
                      "target_door_xyz": [-12, -3.2, 0.5],
                      "cross_doorway_requested": CASES[slug]},
        "controller": {"policy": "approach_halt_door_cycle_resume",
                       "halt_request_frame": 100, "door_open_request_frame": 140,
                       "door_close_request_frame": 420, "resume_request_frame": 480,
                       "passenger_walk_request_frame": 170,
                       "transfer_engineering_target_frame": 260},
        "cameras": [
            {"name": "overview", "xyz": [-12, -17, 18], "pitch": -42, "yaw": 40,
             "size": [1920, 1080], "pose_strategy": "fixed curb and full vehicle overview"},
            {"name": "approach", "xyz": [-2, -11, 8], "pitch": -24, "yaw": 160,
             "size": [1280, 720], "pose_strategy": "fixed approach and sign view"},
            {"name": "reference_corner", "xyz": [-12, -9, 6], "pitch": -24, "yaw": 70,
             "size": [1280, 720], "pose_strategy": "fixed door, curb and passenger view"},
            {"name": "driver_reference", "xyz": [1, 0, 2], "pitch": -8, "yaw": 0,
             "attach_to_ego": True, "size": [1280, 720],
             "pose_strategy": "ego attached driver view"}],
        "rate_hz": RATE_HZ, "duration_s": 30, "planned_frames": FRAMES,
        "original_native_observed": False, "physical_transfer_claimed": False,
        "expeditiousness_conclusion": None,
    }


def validate(scene):
    if scene.get("case") not in CASES:
        raise ValueError("unknown exact loading case")
    root = ET.fromstring(scene["road_opendrive"])
    roads = root.findall("road")
    if root.tag != "OpenDRIVE" or len(roads) != 1 or roads[0].get("id") != "149498":
        raise ValueError("one-way loading road missing")
    road = roads[0]
    objects = road.findall("objects/object")
    signs = road.findall("signals/signal")
    if len(objects) != 1 or objects[0].get("id") != scene["zone"]["object_id"]:
        raise ValueError("marked passenger curb missing")
    if len(signs) != 1 or signs[0].get("id") != scene["zone"]["sign_id"]:
        raise ValueError("effective-hours sign missing")
    if not all(x in signs[0].get("name", "") for x in ("08:00", "18:00", "America/Los_Angeles")):
        raise ValueError("sign schedule differs")
    if scene["zone"]["legal_authority"] != "unverified_original_source":
        raise ValueError("sign authority cannot be presumed")
    if scene["passenger"]["cross_doorway_requested"] is not CASES[scene["case"]]:
        raise ValueError("comparison passenger request differs")
    if tuple(sorted(c["name"] for c in scene["cameras"])) != tuple(sorted(CAMERAS)):
        raise ValueError("four-camera plan missing")
    if any(tuple(c["size"]) != ((1920, 1080) if c["name"] == "overview" else (1280, 720))
           or not c.get("pose_strategy") for c in scene["cameras"]):
        raise ValueError("camera size or pose plan missing")
    if scene["rate_hz"] != RATE_HZ or scene["planned_frames"] != FRAMES or scene["duration_s"] != 30:
        raise ValueError("exact 20 Hz capture plan differs")
    if scene["physical_transfer_claimed"] or scene["original_native_observed"]:
        raise ValueError("authored request cannot claim original observation")
    return {"case": scene["case"], "road_count": 1, "camera_count": 4,
            "planned_frames": FRAMES, "source_request_checked": True,
            "original_native_observed": False}
