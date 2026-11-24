"""Validate a reviewed C110969 local intersection packet against the live map.

No CARLA import occurs here. The caller owns the world and the physical review
of the map packet's boundary and route evidence.
"""

import hashlib
import json
import math
from pathlib import Path

from intersection_geometry import Box, target_pose


PREFIX = "testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver__"
SUFFIXES = {"stop_14ft", "stop_15ft", "stop_16ft", "stand_14ft",
            "traffic_14ft", "police_14ft", "device_14ft"}


def bind(world, packet_path, case_id):
    packet_path = Path(packet_path)
    if not case_id.startswith(PREFIX) or case_id.removeprefix(PREFIX) not in SUFFIXES:
        raise ValueError("Wrong exact case")
    packet_bytes = packet_path.read_bytes()
    packet = json.loads(packet_bytes)
    if packet.get("case_ids") != sorted(PREFIX + suffix for suffix in SUFFIXES):
        raise ValueError("Reviewed packet does not bind all seven exact cases")
    loaded = world.get_map()
    opendrive = loaded.to_opendrive().encode("utf-8")
    digest = hashlib.sha256(opendrive).hexdigest()
    if digest != packet.get("opendrive_sha256"):
        raise ValueError("Loaded OpenDRIVE source hash mismatch")
    if str(loaded.name) != packet.get("map_name"):
        raise ValueError("Loaded map name mismatch")
    if packet.get("geometry_provenance") in (None, "") or \
            not packet.get("boundary_review_source_sha256"):
        raise ValueError("Intersection boundary review source missing")
    bounds = packet["intersection_boundary_local_m"]
    box = Box(*(float(bounds[key]) for key in ("west", "south", "east", "north")))
    if not all(math.isfinite(value) for value in
               (box.west, box.south, box.east, box.north)) or \
            box.west >= box.east or box.south >= box.north:
        raise ValueError("Invalid intersection boundary geometry")
    if packet.get("approach") not in ("east", "west", "north", "south") or \
            not packet.get("route_waypoint_ids") or not packet.get("local_transform_source_sha256"):
        raise ValueError("Reviewed approach/route mapping missing")
    if packet.get("vehicle_length_m", 0) <= 0 or packet.get("vehicle_width_m", 0) <= 0:
        raise ValueError("Reviewed vehicle dimensions missing")
    suffix = case_id.removeprefix(PREFIX)
    gap_ft = int(suffix.split("_")[1].removesuffix("ft"))
    pose = target_pose(box, packet["approach"], gap_ft * 0.3048,
                       packet["vehicle_length_m"], packet["vehicle_width_m"])
    return {"case_id": case_id, "map_name": str(loaded.name),
            "opendrive_sha256": digest,
            "reviewed_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "requested_gap_ft": gap_ft,
            "requested_local_pose": {"x_m": pose[0], "y_m": pose[1],
                                     "heading_deg": pose[2]},
            "boundary_review_claimed": False,
            "physical_realization": "pending"}
