"""Provisional orientation feasibility from the authored CPU OpenDRIVE road.

This checks geometric vehicle footprints only. It does not review a Native map,
prove motion, or turn an engineering sample angle into a legal cutoff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from parking_pose import body


def inspect_straight_lane(path):
    path = Path(path)
    root = ET.fromstring(path.read_text())
    if root.tag != "OpenDRIVE":
        raise ValueError("OpenDRIVE root required")
    roads = root.findall("road")
    if len(roads) != 1:
        raise ValueError("one authored road required")
    road = roads[0]
    geometry = road.findall("./planView/geometry")
    sections = road.findall("./lanes/laneSection")
    offsets = road.findall("./lanes/laneOffset")
    lanes = road.findall("./lanes/laneSection/left/lane")
    if (len(geometry) != 1 or geometry[0].find("line") is None or
            len(sections) != 1 or sections[0].get("s") != "0" or
            len(offsets) != 1 or
            any(float(offsets[0].get(k, "nan")) != 0 for k in ("s", "a", "b", "c", "d")) or
            len(lanes) != 1 or lanes[0].get("type") != "driving" or
            road.findall("./lanes/laneSection/right/lane")):
        raise ValueError("one straight authored driving lane required")
    widths = lanes[0].findall("width")
    if len(widths) != 1 or any(float(widths[0].get(k, "nan")) != 0
                               for k in ("sOffset", "b", "c", "d")):
        raise ValueError("constant authored lane width required")
    width = float(widths[0].get("a", "nan"))
    x = float(geometry[0].get("x", "nan"))
    y = float(geometry[0].get("y", "nan"))
    heading = float(geometry[0].get("hdg", "nan"))
    length = float(geometry[0].get("length", "nan"))
    road_length = float(road.get("length", "nan"))
    start_s = float(geometry[0].get("s", "nan"))
    if not all(map(math.isfinite, (width, x, y, heading, length))) or width <= 0 or length <= 0:
        raise ValueError("positive finite authored dimensions required")
    if not math.isfinite(road_length) or start_s != 0 or road_length != length:
        raise ValueError("authored road and straight geometry extent must agree")
    return {"lane_width_m": width, "road_length_m": length,
            "reference_xy_m": [x, y], "reference_heading_rad": heading,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def candidate_angles(path, *, length_m=4.5, width_m=2.0, spacing_deg=10):
    lane = inspect_straight_lane(path)
    if (not all(math.isfinite(v) for v in (length_m, width_m, spacing_deg)) or
            length_m <= 0 or width_m <= 0 or spacing_deg <= 0 or 90 % spacing_deg):
        raise ValueError("positive dimensions and exact 0..90 spacing required")
    if lane["road_length_m"] < length_m + 2:
        raise ValueError("authored road too short for full vehicle footprint")
    width = lane["lane_width_m"]
    heading = lane["reference_heading_rad"]
    tangent = (math.cos(heading), math.sin(heading))
    normal = (-tangent[1], tangent[0])
    center = tuple(lane["reference_xy_m"][i] +
                   lane["road_length_m"] / 2 * tangent[i] + width / 2 * normal[i]
                   for i in (0, 1))
    samples = []
    for index in range(round(90 / spacing_deg) + 1):
        angle = round(index * spacing_deg, 8)
        rad = math.radians(angle)
        forward = tuple(math.cos(rad) * tangent[i] + math.sin(rad) * normal[i]
                        for i in (0, 1))
        corners = body(center, forward,
                       length_m=length_m, width_m=width_m)
        transverse = length_m * abs(math.sin(rad)) + width_m * abs(math.cos(rad))
        inside = True
        for corner in corners:
            relative = tuple(corner[i] - lane["reference_xy_m"][i] for i in (0, 1))
            along = sum(relative[i] * tangent[i] for i in (0, 1))
            across = sum(relative[i] * normal[i] for i in (0, 1))
            inside &= (-1e-9 <= along <= lane["road_length_m"] + 1e-9 and
                       -1e-9 <= across <= width + 1e-9)
        samples.append({"angle_deg": angle, "transverse_footprint_m": transverse,
                        "full_footprint_inside_authored_lane": inside})
    return {"format": "parking-provisional-orientation-feasibility-v1",
            "source_kind": "authored_synthetic_cpu_opendrive",
            "source_path": str(Path(path)), "source_sha256": lane["source_sha256"],
            "lane_width_m": width, "road_length_m": lane["road_length_m"],
            "vehicle_length_m": length_m, "vehicle_width_m": width_m,
            "spacing_deg": spacing_deg, "samples": samples,
            "all_footprints_fit": all(item["full_footprint_inside_authored_lane"] for item in samples),
            "source_reviewed_native_site": False, "motion_verified": False,
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--opendrive", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = candidate_angles(args.opendrive)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"samples": len(result["samples"]),
                      "all_footprints_fit": result["all_footprints_fit"]}))


if __name__ == "__main__":
    main()
