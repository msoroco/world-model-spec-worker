"""Check an independently reviewed C215286 site packet before Native capture.

The worker does not invent a map polygon, district, or crossing station. The
operator supplies those original sources and this module rejects changed bytes.
"""

import hashlib
import json
import math
from pathlib import Path

from crosswalk_delivery import validate_source


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _transform(entry):
    if not isinstance(entry, dict) or not entry.get("source"):
        raise ValueError("independent transform source required")
    for key in ("xyz", "rpy"):
        values = entry.get(key)
        if not isinstance(values, list) or len(values) != 3 or any(
            type(value) not in (float, int) or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("finite sourced transform required: " + key)


def read(path, case_id):
    """Return a source-bound packet; source document must be a distinct file."""
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("case_id") != case_id:
        raise ValueError("site packet exact case differs")
    source_path = Path(packet.get("site_source_path", ""))
    if not source_path.is_file() or source_path.resolve() == path.resolve():
        raise ValueError("independent original site document required")
    source_bytes = source_path.read_bytes()
    if sha256(source_bytes) != packet.get("site_source_sha256"):
        raise ValueError("original site document hash differs")
    source = json.loads(source_bytes)
    fields = (
        "map_name", "map_sha256", "crosswalk_source", "crosswalk_polygon_xy",
        "vehicle_blueprint_id", "spawn_transform_source", "reverse_route_xy",
        "driver_source", "district_source", "highway_boundary_source",
        "crosswalk_marking_source", "vehicle_class_source", "camera_transforms",
        "spawn_transform",
    )
    for field in fields:
        if packet.get(field) != source.get(field):
            raise ValueError("original site document differs: " + field)
    validate_source(packet)
    if not packet.get("highway_boundary_source") or not packet.get("crosswalk_marking_source") or not packet.get("vehicle_class_source"):
        raise ValueError("highway, marking, and vehicle classification sources required")
    _transform(packet.get("spawn_transform"))
    cameras = packet.get("camera_transforms")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four original camera station sources required")
    for entry in cameras.values():
        _transform(entry)
    return packet, raw, source_bytes


def check_world(world, packet):
    """Bind the site packet to the actual Native OpenDRIVE bytes."""
    map_object = world.get_map()
    if map_object.name != packet["map_name"]:
        raise ValueError("Native map identity differs from reviewed site")
    if sha256(map_object.to_opendrive().encode("utf-8")) != packet["map_sha256"]:
        raise ValueError("Native OpenDRIVE bytes differ from reviewed site")
    return packet["map_sha256"]
