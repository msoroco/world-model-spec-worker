"""Authored cross-traffic signal and lane for the C110919 right turn pair."""
import xml.etree.ElementTree as ET

from geometry import open_drive as base_open_drive, route

TRAFFIC_SIGNAL_ID = "602"
TRAFFIC_APPROACH_ROAD_ID = "3"
TRAFFIC_LANE_ID = "-1"
TRAFFIC_SPAWN_XY_M = (-30.0, -1.75)
TRAFFIC_CONFLICT_X_RANGE_M = (8.0, 12.0)


def open_drive():
    root = ET.fromstring(base_open_drive())
    approach = next(road for road in root.findall("road")
                    if road.attrib["id"] == TRAFFIC_APPROACH_ROAD_ID)
    signals = approach.find("signals")
    ET.SubElement(signals, "signal", id=TRAFFIC_SIGNAL_ID,
                  name="west-approach-circular-green", s="85", t="-3.5",
                  zOffset="4", hOffset="0", pitch="0", roll="0",
                  orientation="+", dynamic="yes", country="US",
                  type="1000001", subtype="0", value="0", unit="")
    root.find("header").set("name", "C110919-red-right-turn-cross-traffic-draft")
    return ET.tostring(root, encoding="unicode")


def check():
    root = ET.fromstring(open_drive())
    signals = root.findall(".//signal")
    if {signal.attrib["id"] for signal in signals} != {"601", TRAFFIC_SIGNAL_ID}:
        raise ValueError("Two independent approach signals required")
    west = next(road for road in root.findall("road")
                if road.attrib["id"] == TRAFFIC_APPROACH_ROAD_ID)
    lane = west.find("lanes/laneSection/right/lane")
    if lane is None or lane.attrib["id"] != TRAFFIC_LANE_ID or \
            west.find("signals/signal").attrib["id"] != TRAFFIC_SIGNAL_ID:
        raise ValueError("West signal or eastbound right lane absent")
    points = route()
    if points[0] != [1.75, -40.0] or points[-1] != [40.0, -1.75]:
        raise ValueError("Ego right-turn route changed")
    return {"cross_traffic_signal_id": TRAFFIC_SIGNAL_ID,
            "cross_traffic_spawn_xy_m": list(TRAFFIC_SPAWN_XY_M),
            "cross_traffic_lane_id": TRAFFIC_LANE_ID,
            "ego_route_samples": len(points),
            "native_signal_direction_verified": False,
            "original_cross_traffic_motion_verified": False,
            "legal_yield_verdict_claimed": False}
