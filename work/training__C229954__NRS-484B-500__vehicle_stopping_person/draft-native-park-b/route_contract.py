"""Validate original designation and route geometry before a Native capture.

The designated extent comes from an independent official-device review. The
route plan is an acquisition input; this module makes no legal determination.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from designated_stop import _overlap, _polygon, _area


def _point3(value):
    if (not isinstance(value, list) or len(value) != 3 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) for v in value)):
        raise ValueError("Missing finite sourced route point")
    return tuple(float(v) for v in value)


def _read_ref(ref, label):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("Missing " + label + " source reference")
    path = Path(ref["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("Missing or changed " + label + " source")
    return json.loads(path.read_text())


def validate(source, condition):
    """Return a measured target only after every independent source joins."""
    if condition not in ("condition_a", "condition_b"):
        raise ValueError("Unknown exact comparison condition")
    if source.get("source_kind") != "original_official_device_review":
        raise ValueError("Original official device review required")
    refs = source.get("sources", {})
    device = _read_ref(refs.get("device"), "device")
    designation = _read_ref(refs.get("designation"), "designation")
    route = _read_ref(refs.get("route"), "route")
    map_record = _read_ref(refs.get("map"), "map")
    if not all(record.get("map_name") == source.get("map_name") for record in
               (device, designation, route, map_record)):
        raise ValueError("Device, designation, route or map identity differs")
    if not source.get("map_name") or not source.get("device_id") or \
            device.get("device_id") != source["device_id"] or \
            designation.get("device_id") != source["device_id"]:
        raise ValueError("Original device identity missing or mismatched")
    if device.get("authority_status") != "source_reviewed_official" or \
            not device.get("content") or device.get("erected") is not True or \
            not device.get("authority_source") or not device.get("content_source"):
        raise ValueError("Original official device authority, content or erection missing")
    if device.get("active_first_frame") != 0 or device.get("active_last_frame") != 599:
        raise ValueError("Official device does not cover the 600-frame capture")
    if not designation.get("designation_source") or \
            designation.get("device_id") != device.get("device_id"):
        raise ValueError("Independent designated extent source missing")
    if not map_record.get("hazard_context_source") or \
            not map_record.get("physical_hazard_or_congestion_facts"):
        raise ValueError("Physical hazardous or congested context missing")
    polygon = _polygon(designation.get("designated_polygon_map_m"))
    if route.get("device_id") != device["device_id"]:
        raise ValueError("Route and device identity differs")
    if route.get("person_caused_stop_source") in (None, "") or \
            route.get("traffic_and_direction_source") in (None, ""):
        raise ValueError("Person, traffic or direction source missing")
    targets = route.get("stop_targets", {})
    if set(targets) != {"condition_a", "condition_b"}:
        raise ValueError("Both exact stop targets required")
    checked = {}
    for name, target in targets.items():
        point = _point3(target.get("location_xyz_m"))
        footprint = _polygon(target.get("vehicle_footprint_map_m"))
        if not target.get("drivable_lane_source") or not target.get("route_alignment_source"):
            raise ValueError("Original drivable lane and route alignment source missing")
        if target.get("person_caused_stop") is not True:
            raise ValueError("Person-caused destination stop missing")
        overlap = _overlap(footprint, polygon) / _area(footprint)
        if name == "condition_a" and overlap <= 0.0:
            raise ValueError("Condition A body misses designated extent")
        if name == "condition_b" and overlap > 0.0:
            raise ValueError("Condition B body enters designated extent")
        checked[name] = {"location_xyz_m": point, "overlap_fraction": overlap,
                         "route_alignment_source": target["route_alignment_source"]}
    if route.get("fixed_context_id") in (None, ""):
        raise ValueError("Comparison fixed context identity missing")
    approach = route.get("approach_waypoints_xyz_m")
    if not isinstance(approach, list) or len(approach) < 2:
        raise ValueError("Sourced approach waypoints missing")
    approach = [_point3(point) for point in approach]
    if any(math.dist(a, b) > 25.0 or math.dist(a, b) < 0.05
           for a, b in zip(approach, approach[1:])):
        raise ValueError("Sourced approach waypoints discontinuous")
    if any(math.dist(approach[-1], checked[name]["location_xyz_m"]) > 20.0
           for name in checked):
        raise ValueError("Stop targets differ from sourced approach")
    return {"map_name": source["map_name"], "device_id": device["device_id"],
            "condition": condition, "target_xyz_m": checked[condition]["location_xyz_m"],
            "approach_waypoints_xyz_m": approach,
            "overlap_fraction": checked[condition]["overlap_fraction"],
            "fixed_context_id": route["fixed_context_id"],
            "source_hashes": {key: ref["sha256"] for key, ref in refs.items()},
            "legal_characterization": "unassessed", "physical_completion": False}
