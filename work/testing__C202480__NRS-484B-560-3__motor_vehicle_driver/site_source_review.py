"""Check retained OpenDRIVE lane evidence for the 560(3) marked-lane branch.

This is an engineering source check. It does not certify a crossing device,
highway ownership, driver duty, or legal meaning of the marking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(packet_path: Path, entry: dict) -> Path:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError("retained OpenDRIVE source declaration missing")
    relative = Path(entry["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("OpenDRIVE source path escapes packet")
    source = (packet_path.parent / relative).resolve()
    if packet_path.parent.resolve() not in source.parents or not source.is_file():
        raise ValueError("retained OpenDRIVE source missing")
    if sha(source) != entry.get("sha256"):
        raise ValueError("retained OpenDRIVE source hash differs")
    return source


def inspect(packet_path: Path) -> dict:
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    source = _source(packet_path, packet.get("sources", {}).get("opendrive"))
    try:
        root = ET.fromstring(source.read_bytes())
    except ET.ParseError as error:
        raise ValueError("retained OpenDRIVE XML invalid") from error
    if root.tag != "OpenDRIVE":
        raise ValueError("retained source is not OpenDRIVE")
    road_id = packet.get("opendrive_road_id")
    station = packet.get("opendrive_lane_section_s_m")
    if (not isinstance(road_id, str) or not road_id or
            type(station) not in (int, float) or not math.isfinite(station) or station < 0):
        raise ValueError("reviewed road and lane-section station required")
    roads = [item for item in root.findall("road") if item.get("id") == road_id]
    if len(roads) != 1:
        raise ValueError("selected highway road absent or ambiguous in OpenDRIVE")
    road = roads[0]
    try:
        length = float(road.attrib["length"])
    except (KeyError, ValueError) as error:
        raise ValueError("selected OpenDRIVE road length invalid") from error
    if not math.isfinite(length) or not 0 <= station < length:
        raise ValueError("lane-section station outside selected highway road")
    sections = road.findall("./lanes/laneSection")
    try:
        starts = [float(item.attrib["s"]) for item in sections]
    except (KeyError, ValueError) as error:
        raise ValueError("OpenDRIVE lane-section station invalid") from error
    if (not sections or any(not math.isfinite(s) for s in starts) or
            starts != sorted(starts) or len(starts) != len(set(starts))):
        raise ValueError("OpenDRIVE lane sections missing or unordered")
    selected = [item for i, item in enumerate(sections)
                if starts[i] <= station and (i + 1 == len(starts) or station < starts[i + 1])]
    if len(selected) != 1:
        raise ValueError("selected highway lane section absent")
    candidates = {}
    for side in ("left", "right"):
        for lane in selected[0].findall(f"./{side}/lane"):
            if lane.get("type") != "driving":
                continue
            try:
                lane_id = int(lane.attrib["id"])
            except (KeyError, ValueError) as error:
                raise ValueError("OpenDRIVE driving lane identity invalid") from error
            if lane_id == 0 or lane_id in candidates or (lane_id > 0) != (side == "left"):
                raise ValueError("OpenDRIVE driving lane side or identity invalid")
            marks = lane.findall("roadMark")
            if not marks or any(mark.get("type") in (None, "none") for mark in marks):
                raise ValueError("OpenDRIVE driving lane lacks explicit road marking")
            candidates[lane_id] = {"lane_id": lane_id, "side": side,
                                   "marking_types": sorted({mark.attrib["type"] for mark in marks})}
    declared = packet.get("marked_lanes")
    if not isinstance(declared, list) or not declared:
        raise ValueError("declared marked highway lanes missing")
    try:
        declared_ids = [item["opendrive_lane_id"] for item in declared]
    except (TypeError, KeyError) as error:
        raise ValueError("declared lane lacks OpenDRIVE identity") from error
    if any(type(value) is not int for value in declared_ids) or set(declared_ids) != set(candidates) or len(declared_ids) != len(candidates):
        raise ValueError("declared total marked highway lanes differ from OpenDRIVE")
    return {"format": "c202480-opendrive-marked-lane-review-v1",
            "case_id": packet.get("case_id"), "site_packet_sha256": sha(packet_path),
            "opendrive_sha256": sha(source), "road_id": road_id,
            "lane_section_s_m": float(station), "marked_highway_lane_count": len(candidates),
            "lanes": [candidates[key] for key in sorted(candidates)],
            "lane_directions_verified": False, "crossing_authority_verified": False,
            "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-packet", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.site_packet), indent=2))
