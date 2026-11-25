"""Read the authored same-cell junction and inventory every entering lane.

The OpenDRIVE file is a CPU construction source. Its sign codes and highway
classification still require Native and original-camera review after capture.
"""

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET


SIGN_TYPES = {"205": "yield", "206": "stop"}


def inventory(path: Path) -> dict:
    path = Path(path)
    root = ET.parse(path).getroot()
    if root.tag != "OpenDRIVE":
        raise ValueError("Authored site is not OpenDRIVE")
    roads = {road.get("id"): road for road in root.findall("road")}
    junction = root.find("./junction[@id='158191']")
    if junction is None or set(roads) != {"158190", "158192", "158193", "158194", "158195", "158196"}:
        raise ValueError("Wrong C158196 junction roads")
    expected = {("158190", "-1"), ("158194", "-1"), ("158196", "1")}
    incoming = set()
    for connection in junction.findall("connection"):
        road_id = connection.get("incomingRoad")
        if road_id not in roads:
            raise ValueError("Unknown incoming road")
        for link in connection.findall("laneLink"):
            key = (road_id, link.get("from"))
            if key in incoming:
                raise ValueError("Duplicate incoming lane")
            incoming.add(key)
    if incoming != expected:
        raise ValueError("Incomplete or changed entering lanes")
    ego_lanes = roads["158190"].findall("./lanes/laneSection/right/lane")
    through_lanes = roads["158194"].findall("./lanes/laneSection/left/lane") + roads["158194"].findall("./lanes/laneSection/right/lane")
    if (len(ego_lanes) != 1 or ego_lanes[0].get("id") != "-1" or
            {lane.get("id") for lane in through_lanes} != {"-1", "1"}):
        raise ValueError("Authored one-way to two-way layout changed")
    entries = []
    for road_id, lane_id in sorted(incoming):
        devices = []
        for signal in roads[road_id].findall("./signals/signal"):
            if signal.get("dynamic") != "no":
                continue
            validity = signal.find("validity")
            if validity is None or validity.get("fromLane") != lane_id or validity.get("toLane") != lane_id:
                continue
            if signal.get("type") not in SIGN_TYPES:
                raise ValueError("Unsupported static sign on entering lane")
            devices.append((SIGN_TYPES[signal.get("type")], signal.get("id")))
        if len(devices) > 1:
            raise ValueError("Multiple governing static signs on entrance")
        device, sign_id = devices[0] if devices else ("none", None)
        entries.append({"lane_key": road_id + ":" + lane_id, "device": device,
                        "device_source": path.name + ("#" + sign_id if sign_id else "#no-static-sign-on-" + road_id + ":" + lane_id)})
    ego_device = next(item["device"] for item in entries if item["lane_key"] == "158190:-1")
    other_device = next(item["device"] for item in entries if item["lane_key"] == "158194:-1")
    if ego_device not in {"stop", "yield"} or other_device != "none":
        raise ValueError("Signed ego or non-obligated other entrance changed")
    dynamic = [(road_id, signal) for road_id, road in roads.items()
               for signal in road.findall("./signals/signal")
               if signal.get("dynamic") == "yes"]
    controls = root.findall("./controller/control")
    if (len(dynamic) != 1 or len(controls) != 1 or
            controls[0].get("signalId") != dynamic[0][1].get("id")):
        raise ValueError("Signal control chain changed")
    head_road, head = dynamic[0]
    validity = head.find("validity")
    if validity is None or validity.get("fromLane") != validity.get("toLane"):
        raise ValueError("Signal affected lane missing")
    head_lane = head_road + ":" + validity.get("fromLane")
    if head_lane not in {road + ":" + lane for road, lane in incoming}:
        raise ValueError("Signal governs no inventoried entrance")
    return {"source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "native_map_id": root.find("header").get("name"),
            "junction_id": 158191, "non_through_highway": True,
            "highway_status_source": path.name + "#authored-non-through-junction",
            "legal_site_review_pending": True,
            "all_entrances_inventoried": True, "entrances": entries,
            "ego_lane_key": "158190:-1", "other_lane_key": "158194:-1",
            "intersection_polygon_xy_m": [[-8, -8], [8, -8], [8, 8], [-8, 8]],
            "intersection_boundary_source": path.name + "#158192,158195",
            "conflict_point_xy_m": [0, 0],
            "conflict_point_source": path.name + "#158192,158195-crossing",
            "complete_body_observation_source": "original-Native-actor-bounding-box-vertices",
            "signal_head_source": path.name + "#" + head.get("id"),
            "signal_head_lane_key": head_lane,
            "authored_signal_governs_ego": head_lane == "158190:-1",
            "native_signal_governance_review_pending": True}
