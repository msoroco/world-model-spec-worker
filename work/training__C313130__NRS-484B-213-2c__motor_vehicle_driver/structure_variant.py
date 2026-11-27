"""Authored bridge and viaduct approaches on the fixed C313130 corridor.

These are additional scene variants of the assigned tunnel cell. They specify
drivable raised road geometry and distinct support inventories, but require
original Native readback and pixels before either structure can be identified.
"""

import json
import xml.etree.ElementTree as ET

from tunnel_scene import open_drive


KINDS = {
    "bridge": {"deck_start_x_m": -30.0, "deck_end_x_m": -10.0,
               "support_x_m": [-30.0, -10.0], "span_count": 1},
    "viaduct": {"deck_start_x_m": -30.0, "deck_end_x_m": 10.0,
                "support_x_m": [-30.0, -20.0, -10.0, 0.0, 10.0],
                "span_count": 4},
}


def _smooth(profile, start_s, end_s, start_z, end_z):
    length = end_s - start_s
    height = end_z - start_z
    ET.SubElement(profile, "elevation", s=str(start_s), a=str(start_z),
                  b="0", c=str(3 * height / length ** 2),
                  d=str(-2 * height / length ** 3))


def road_xml(kind):
    if kind not in KINDS:
        raise ValueError("Unknown statutory structure alternative")
    spec = KINDS[kind]
    root = ET.fromstring(open_drive())
    road = root.find("road")
    road.set("name", "C313130_tunnel_corridor_" + kind + "_approach")
    profile = road.find("elevationProfile")
    profile.clear()
    _smooth(profile, 0, 40, 0, 0)
    _smooth(profile, 40, 70, 0, 4)
    deck_end_s = spec["deck_end_x_m"] + 100
    _smooth(profile, 70, deck_end_s, 4, 4)
    _smooth(profile, deck_end_s, deck_end_s + 30, 4, 0)
    _smooth(profile, deck_end_s + 30, 200, 0, 0)
    return ET.tostring(root, encoding="unicode")


def request(kind, side):
    if kind not in KINDS or side not in ("right", "left"):
        raise ValueError("Unknown structure or lateral target")
    spec = KINDS[kind]
    return {"format": "worker-c313130-structure-variant-request",
            "cell_id": "C313130", "frozen_layout": "tunnel",
            "structure_kind_requested": kind,
            "road_opendrive": road_xml(kind),
            "deck_start_x_m": spec["deck_start_x_m"],
            "deck_end_x_m": spec["deck_end_x_m"],
            "deck_height_m": 4.0,
            "support_x_m": spec["support_x_m"],
            "span_count": spec["span_count"],
            "tunnel_portal_x_m": 60.0,
            "requested_lateral_target": side,
            "target_y_m": -1.75 if side == "right" else 1.75,
            "rate_hz": 20, "duration_frames": 600,
            "physical_structure_verified": False,
            "legal_view_obstructed": "independent_judgment_required"}


def validate(value):
    kind = value.get("structure_kind_requested")
    if kind not in KINDS or value.get("cell_id") != "C313130" or value.get("frozen_layout") != "tunnel":
        raise ValueError("Structure variant identity changed")
    spec = KINDS[kind]
    if (value.get("deck_start_x_m"), value.get("deck_end_x_m"),
            value.get("support_x_m"), value.get("span_count")) != (
            spec["deck_start_x_m"], spec["deck_end_x_m"],
            spec["support_x_m"], spec["span_count"]):
        raise ValueError("Bridge or viaduct geometry differs")
    if value.get("rate_hz") != 20 or value.get("duration_frames") != 600 or value.get("physical_structure_verified") is not False:
        raise ValueError("Structure capture contract changed")
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if road is None or road.get("id") != "313130":
        raise ValueError("Fixed road identity lost")
    lane_ids = {lane.get("id") for lane in road.findall("lanes/laneSection/*/lane")}
    if lane_ids != {"-1", "0", "1"}:
        raise ValueError("Fixed opposed-lane road lost")
    starts = [float(e.get("s")) for e in road.findall("elevationProfile/elevation")]
    if starts != [0, 40, 70, spec["deck_end_x_m"] + 100,
                  spec["deck_end_x_m"] + 130]:
        raise ValueError("Raised drivable deck profile missing")
    return {"kind": kind, "span_count": spec["span_count"],
            "physical_structure_verified": False}


if __name__ == "__main__":
    print(json.dumps([validate(request(kind, side)) for kind in KINDS
                      for side in ("right", "left")]))
