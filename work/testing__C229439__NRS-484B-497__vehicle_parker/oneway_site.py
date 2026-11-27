"""Review original one-way-road and device sources before Native construction.

The source record supplies facts for later independent review. This module checks
identity, geometry and hashes; it does not decide what Nevada law permits.
"""

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229439__NRS-484B-497__vehicle_parker"
KINDS = {"none", "official_park_permit", "official_stand_permit",
         "official_restrict", "unofficial_park_permit"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(not isinstance(x, (int, float)) or isinstance(x, bool) or
                not math.isfinite(x) for x in value)):
        raise ValueError("finite map point required")
    return value


def _polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("roadway polygon required")
    return [_point(point) for point in value]


def _inside(point, polygon):
    x, y = _point(point)
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if ((a[1] > y) != (b[1] > y) and
                x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]):
            inside = not inside
    return inside


def load_site(site_path, case_id):
    path = Path(site_path).resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if site.get("assignment_id") != ASSIGNMENT or site.get("case_id") != case_id:
        raise ValueError("reviewed site has wrong exact assignment or case")
    source_names = ("map", "roadway", "restriction", "device_inventory",
                    "authority", "purpose", "person")
    sources = site.get("sources")
    if not isinstance(sources, dict) or set(source_names) - set(sources):
        raise ValueError("missing original site source packet")
    records = {}
    for name in source_names:
        ref = sources[name]
        rel = ref.get("path")
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("site source must be relative to reviewed site")
        target = (path.parent / rel).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file():
            raise ValueError("reviewed site source absent: " + name)
        if sha(target) != ref.get("sha256"):
            raise ValueError("reviewed site source hash differs: " + name)
        records[name] = json.loads(target.read_text(encoding="utf-8"))
    road = records["roadway"]
    polygon = _polygon(road.get("roadway_polygon_xy"))
    forward = _point(road.get("forward_xy"))
    if abs(math.hypot(*forward) - 1) > .02:
        raise ValueError("road forward vector must be unit length")
    origin = _point(road.get("origin_xy"))
    lanes = road.get("marked_lanes")
    if not isinstance(lanes, list) or not lanes:
        raise ValueError("reviewed marked-lane inventory required")
    lane_ids = [lane.get("lane_id") for lane in lanes]
    if any(not isinstance(n, int) or n == 0 for n in lane_ids) or len(set(lane_ids)) != len(lane_ids):
        raise ValueError("unique nonzero Native lane IDs required")
    if not all(lane.get("marking_source") and lane.get("direction_source") and
               isinstance(lane.get("direction_with_forward"), bool) for lane in lanes):
        raise ValueError("marked-lane direction and source required")
    restriction = records["restriction"]
    if (restriction.get("one_way") not in (True, False) or
            not restriction.get("authority_source") or
            not restriction.get("scope_source")):
        raise ValueError("one-way restriction source incomplete")
    device = records["device_inventory"]
    if (device.get("kind") not in KINDS or
            not isinstance(device.get("devices"), list) or
            not device.get("inventory_source")):
        raise ValueError("device inventory incomplete")
    if device["kind"] == "none":
        if device["devices"]:
            raise ValueError("no-device inventory contains device")
    else:
        if len(device["devices"]) != 1:
            raise ValueError("one source-bound device required")
        item = device["devices"][0]
        for key in ("device_id", "instruction_source", "erection_source",
                    "official_status_source", "governed_space_source",
                    "prop_blueprint_id", "prop_pose"):
            if not item.get(key):
                raise ValueError("source-bound device field absent: " + key)
        _polygon(item.get("governed_space_polygon_xy"))
    if not records["authority"].get("source") or not records["purpose"].get("source") or not records["person"].get("source"):
        raise ValueError("authority, purpose and person sources required")
    target = _point(site.get("target_xy"))
    start = _point(site.get("approach_xy"))
    if math.dist(target, start) < 8 or not _inside(target, polygon):
        raise ValueError("source-bound roadway target/approach geometry invalid")
    if not isinstance(site.get("target_heading_deg"), (int, float)):
        raise ValueError("target heading required")
    return site, records
