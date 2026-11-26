"""Authored crossroad, governing stop sign, actors, controls and capture request."""

import math
import xml.etree.ElementTree as ET

CASES = {
    "complete_stop_then_yield", "roll_through_conflict",
    "yield_sign_slow_then_yield", "yield_sign_no_slow_conflict",
    "yield_sign_crosswalk_no_line", "yield_sign_viewpoint_no_line_crosswalk",
    "stop_before_crosswalk_no_line", "stop_at_viewpoint_no_line_crosswalk",
    "approaching_through_hazard", "through_occupancy_during_crossing",
    "police_directed_control", "signal_directed_control",
}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def open_drive(sign="stop", reference="stop_line", signal_control=False):
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C111325-stop-through-crossroad",
                  version="1", north="100", south="-100", east="100", west="-100", vendor="full-train-worker")
    for road_id, road_name, x, y, heading in ((111325, "stop_approach", -80, 0, 0),
                                              (111326, "through_highway", 0, -80, 1.57079632679)):
        road = ET.SubElement(root, "road", id=str(road_id), name=road_name, length="160", junction="-1")
        ET.SubElement(road, "link")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x=str(x), y=str(y),
                             hdg=str(heading), length="160")
        ET.SubElement(geom, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, ident in (("left", 1), ("center", 0), ("right", -1)):
            lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(ident),
                                 type="none" if ident == 0 else "driving", level="false")
            if ident:
                ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        objects = ET.SubElement(road, "objects")
        if road_id == 111325 and reference == "stop_line":
            ET.SubElement(objects, "object", id="line-111325", name="marked-stop-line",
                          type="roadMark", s="74", t="0", zOffset="0", hdg="0",
                          length="0.4", width="7", height="0")
        if road_id == 111325 and reference == "crosswalk":
            ET.SubElement(objects, "object", id="crosswalk-111325", name="near-side-crosswalk",
                          type="crosswalk", s="75", t="0", zOffset="0", hdg="0",
                          length="1", width="7", height="0")
        signals = ET.SubElement(road, "signals")
        if road_id == 111325:
            ET.SubElement(signals, "signal", id=sign + "-111325", s="74", t="-3.7", name=sign.upper(),
                          dynamic="no", orientation="+", zOffset="0", country="US",
                          type="205" if sign == "yield" else "206", subtype="0",
                          value="0", unit="", height="0.8", width="0.8")
            if signal_control:
                ET.SubElement(signals, "signal", id="traffic-signal-111325", s="75", t="-3.7",
                              name="TRAFFIC_SIGNAL", dynamic="yes", orientation="+", zOffset="0",
                              country="US", type="1000001", subtype="0", value="0", unit="",
                              height="3", width="0.5")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown stop/yield case")
    sign = "yield" if case.startswith("yield_sign_") else "stop"
    has_line = case not in {"stop_before_crosswalk_no_line", "stop_at_viewpoint_no_line_crosswalk",
                            "yield_sign_crosswalk_no_line", "yield_sign_viewpoint_no_line_crosswalk"}
    has_crosswalk = case in {"stop_before_crosswalk_no_line", "yield_sign_crosswalk_no_line"}
    police = case == "police_directed_control"
    signal = case == "signal_directed_control"
    reference = "stop_line" if has_line else "crosswalk" if has_crosswalk else "nearest_viewpoint"
    return {"format": "worker-authored-stop-yield-request", "case": case,
            "road_opendrive": open_drive(sign, reference, signal), "stop_line_x_m": -6 if has_line else None,
            "intersection_near_x_m": -3.5, "intersection_far_x_m": 3.5,
            "stop_line_marking": {"endpoints_xy_m": [[-6, -3.5], [-6, 0]], "width_m": 0.4} if has_line else None,
            "crosswalk_marking": {"near_edge_x_m": -5.5, "far_edge_x_m": -4.5, "width_m": 3.5} if has_crosswalk else None,
            "nearest_viewpoint_candidate": {"front_x_m": -4.1, "source_required": "original through-highway sight-distance rays"} if reference == "nearest_viewpoint" else None,
            "stopping_reference": reference,
            "governing_sign": sign + "-111325", "police_controlling": police, "signal_controlling": signal,
            "control_exception_source_required": "original officer direction" if police else "original signal state" if signal else None,
            "police_actor_request": {"blueprint_filter": "walker.pedestrian.*", "xyz": [-3, -5, 0.5],
                                     "direction_xy": [1, 0], "source_required": "independently reviewed officer identity and traffic direction"} if police else None,
            "signal_controller_request": {"signal_id": "traffic-signal-111325", "planned_phase": "source_readback_required",
                                          "source_required": "original governing signal state on every frame"} if signal else None,
            "ego": {"blueprint": "vehicle.tesla.model3", "start_xyz": [-45, -1.75, 0.5],
                    "heading_deg": 0, "body_length_m": 4.5},
            "through_vehicle": {"blueprint": "vehicle.tesla.model3",
                                "start_xyz": [1.75, -100 if case == "approaching_through_hazard" else -65 if case == "through_occupancy_during_crossing" else -50, 0.5],
                                "heading_deg": 90, "requested_speed_mps": 5},
            "controller": {"policy": "roll_through" if case in {"roll_through_conflict", "yield_sign_no_slow_conflict"} else "stop_release",
                           "stop_front_x_m": -7 if has_line else -6 if has_crosswalk else -4.1,
                           "release_frame": 250,
                           "requested_yield_action": case in {"complete_stop_then_yield", "yield_sign_slow_then_yield", "stop_before_crosswalk_no_line", "stop_at_viewpoint_no_line_crosswalk", "yield_sign_crosswalk_no_line", "yield_sign_viewpoint_no_line_crosswalk", "approaching_through_hazard", "through_occupancy_during_crossing"}},
            "cameras": [
                {"name": "overview", "xyz": [-14, -14, 20], "pitch": -45, "yaw": 35,
                 "width": 1920, "height": 1080, "fov_deg": 80, "pose_strategy": "fixed surveyed intersection view"},
                {"name": "approach", "xyz": [-20, -10, 9], "pitch": -20, "yaw": 25,
                 "width": 1280, "height": 720, "fov_deg": 80, "pose_strategy": "fixed surveyed governed approach view"},
                {"name": "reference_corner", "xyz": [-8, -11, 6], "pitch": -20, "yaw": 30,
                 "width": 1280, "height": 720, "fov_deg": 80, "pose_strategy": "fixed surveyed stop or yield reference view"},
                {"name": "driver_reference", "xyz": [1, 0, 2], "pitch": -8, "yaw": 0,
                 "attach_to_ego": True, "width": 1280, "height": 720, "fov_deg": 80,
                 "pose_strategy": "attached driver approach and through-highway view"}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_geometry_verified": False, "physical_success_claimed": False}


def validate(requested):
    root = ET.fromstring(requested["road_opendrive"])
    roads = root.findall("road")
    if root.tag != "OpenDRIVE" or {r.attrib["id"] for r in roads} != {"111325", "111326"}:
        raise ValueError("Two-road intersection missing")
    by_id = {road.attrib["id"]: road for road in roads}
    approach = by_id["111325"].find("planView/geometry")
    through = by_id["111326"].find("planView/geometry")
    if approach is None or through is None or approach.find("line") is None or through.find("line") is None:
        raise ValueError("Straight crossing road geometry missing")
    if (abs(float(approach.attrib["y"])) > 1e-6 or
            abs(float(through.attrib["x"])) > 1e-6 or
            abs(math.sin(float(through.attrib["hdg"]) - float(approach.attrib["hdg"])) - 1) > 1e-6):
        raise ValueError("Perpendicular through-highway geometry missing")
    if (requested["ego"]["start_xyz"][0] >= requested["intersection_near_x_m"] or
            abs(requested["ego"]["start_xyz"][1] + 1.75) > .5 or
            requested["through_vehicle"]["start_xyz"][1] >= -4 or
            abs(requested["through_vehicle"]["start_xyz"][0] - 1.75) > .5):
        raise ValueError("Actors not placed on governed approach and through highway")
    sign = by_id["111325"].find("signals/signal")
    if sign is None or sign.attrib.get("id") != requested["governing_sign"] or sign.attrib.get("name") not in {"STOP", "YIELD"}:
        raise ValueError("Governing sign missing")
    reference = requested["stopping_reference"]
    if reference == "stop_line":
        objects = by_id["111325"].findall("objects/object")
        if (requested["stop_line_marking"] is None or
                requested["stop_line_marking"]["endpoints_xy_m"][0][0] != requested["stop_line_x_m"] or
                len(objects) != 1 or objects[0].attrib.get("name") != "marked-stop-line" or
                objects[0].attrib.get("type") != "roadMark" or
                abs(float(objects[0].attrib["s"]) + float(approach.attrib["x"]) - requested["stop_line_x_m"]) > 1e-6):
            raise ValueError("Marked stop line missing")
    elif reference == "crosswalk":
        objects = by_id["111325"].findall("objects/object")
        if (requested["stop_line_marking"] is not None or requested["crosswalk_marking"] is None or
                len(objects) != 1 or objects[0].attrib.get("name") != "near-side-crosswalk" or
                objects[0].attrib.get("type") != "crosswalk"):
            raise ValueError("Near-side crosswalk hierarchy invalid")
    elif reference == "nearest_viewpoint":
        if (requested["stop_line_marking"] is not None or requested["crosswalk_marking"] is not None or
                requested["nearest_viewpoint_candidate"] is None or
                by_id["111325"].findall("objects/object")):
            raise ValueError("Nearest-viewpoint hierarchy invalid")
    else:
        raise ValueError("Unknown stopping reference")
    if len(requested["cameras"]) != 4 or set(c["name"] for c in requested["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    sizes = {"overview": (1920, 1080), "approach": (1280, 720),
             "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    if any((c.get("width"), c.get("height")) != sizes[c["name"]] or not c.get("pose_strategy") or not c.get("fov_deg")
           for c in requested["cameras"]):
        raise ValueError("Camera profile or pose strategy differs")
    if requested["planned_frames"] != 600 or requested["rate_hz"] != 20:
        raise ValueError("30-second capture request missing")
    if requested["police_controlling"] and requested["signal_controlling"]:
        raise ValueError("Two simultaneous controlling exceptions unsupported")
    if (requested["police_controlling"] or requested["signal_controlling"]) and not requested["control_exception_source_required"]:
        raise ValueError("Control exception source missing")
    if requested["police_controlling"]:
        actor = requested.get("police_actor_request")
        if not isinstance(actor, dict) or not actor.get("blueprint_filter") or not actor.get("source_required") or len(actor.get("xyz", [])) != 3:
            raise ValueError("Controlling officer actor request missing")
    elif requested.get("police_actor_request") is not None:
        raise ValueError("Unrequested controlling officer")
    if requested["signal_controlling"]:
        signal_request = requested.get("signal_controller_request")
        sources = by_id["111325"].findall("signals/signal")
        if (not isinstance(signal_request, dict) or not signal_request.get("source_required") or
                len(sources) != 2 or sources[1].attrib.get("id") != signal_request.get("signal_id") or
                sources[1].attrib.get("dynamic") != "yes"):
            raise ValueError("Controlling signal construction or source missing")
    elif requested.get("signal_controller_request") is not None:
        raise ValueError("Unrequested controlling signal")
    if requested["native_geometry_verified"]:
        raise ValueError("Unsourced Native claim")
    return {"case": requested["case"], "road_count": 2, "camera_count": 4,
            "planned_frames": 600, "stopping_reference": reference,
            "control_exception": "police" if requested["police_controlling"] else "signal" if requested["signal_controlling"] else None,
            "authored_request_checked": True, "native_geometry_verified": False}
