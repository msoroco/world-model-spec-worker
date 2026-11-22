"""CPU check of diagnostic route anchors against engineering OpenDRIVE lanes.

This is geometric and topological screening, not a Native waypoint or legal check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _road_samples(road):
    lanes = road.findall("./lanes/laneSection/right/lane")
    driving = [lane for lane in lanes if lane.get("id") == "-1" and lane.get("type") == "driving"]
    if len(driving) != 1:
        raise ValueError(f"road {road.get('id')} lacks one right driving lane")
    width = driving[0].find("width")
    if width is None or any(float(width.get(k, "0")) != 0 for k in ("b", "c", "d")):
        raise ValueError("nonconstant lane width needs Native binding")
    offset = float(width.get("a")) / 2
    if not 0 < offset <= 5:
        raise ValueError("invalid driving lane width")
    samples = []
    for geometry in road.findall("./planView/geometry"):
        start = float(geometry.get("s"))
        x, y, heading, length = (float(geometry.get(k)) for k in ("x", "y", "hdg", "length"))
        arc = geometry.find("arc")
        if geometry.find("line") is None and arc is None:
            raise ValueError("unsupported geometry primitive")
        curvature = float(arc.get("curvature")) if arc is not None else 0.0
        for n in range(max(1, math.ceil(length / 0.1)) + 1):
            ds = min(length, n * 0.1)
            angle = heading + curvature * ds
            if curvature:
                cx = x + (math.sin(angle) - math.sin(heading)) / curvature
                cy = y - (math.cos(angle) - math.cos(heading)) / curvature
            else:
                cx = x + ds * math.cos(heading)
                cy = y + ds * math.sin(heading)
            samples.append((cx + offset * math.sin(angle),
                            cy - offset * math.cos(angle), start + ds))
    return samples


def _edges(root, roads):
    edges = {road_id: set() for road_id in roads}
    for road_id, road in roads.items():
        successor = road.find("./link/successor")
        if successor is not None and successor.get("elementType") == "road":
            target = successor.get("elementId")
            if target not in roads:
                raise ValueError("successor road missing")
            edges[road_id].add(target)
    for connection in root.findall("./junction/connection"):
        incoming = connection.get("incomingRoad")
        connecting = connection.get("connectingRoad")
        if incoming not in roads or connecting not in roads:
            raise ValueError("junction connection road missing")
        if not any(link.get("from") == "-1" and link.get("to") == "-1"
                   for link in connection.findall("laneLink")):
            raise ValueError("junction lacks driving lane link")
        edges[incoming].add(connecting)
    return edges


def _reachable(edges, first, second):
    pending = list(edges[first])
    seen = set()
    while pending:
        item = pending.pop()
        if item == second:
            return True
        if item not in seen:
            seen.add(item)
            pending.extend(edges[item])
    return False


def preflight(map_path, scenes, tolerance_m=0.9):
    data = Path(map_path).read_bytes()
    root = ET.fromstring(data)
    if root.tag != "OpenDRIVE":
        raise ValueError("source is not OpenDRIVE")
    roads = {road.get("id"): road for road in root.findall("road")}
    if len(roads) != len(root.findall("road")):
        raise ValueError("duplicate road ID")
    samples = {road_id: _road_samples(road) for road_id, road in roads.items()}
    edges = _edges(root, roads)
    digest = hashlib.sha256(data).hexdigest()
    cases = {}
    for scene_path in scenes:
        scene = json.loads(Path(scene_path).read_text())
        if scene["crossing"]["map_source_sha256"] != digest:
            raise ValueError(f"{scene_path}: map source SHA mismatch")
        parties = {}
        for party in ("ego", "other"):
            candidates = []
            for point in scene[f"{party}_route_xy_m"]:
                nearest = []
                for road_id, lane_samples in samples.items():
                    x, y, s = min(lane_samples, key=lambda item: math.hypot(item[0]-point[0], item[1]-point[1]))
                    distance = math.hypot(x-point[0], y-point[1])
                    if distance <= tolerance_m:
                        nearest.append((road_id, s, round(distance, 3)))
                if not nearest:
                    raise ValueError(f"{scene_path}: {party} route anchor is off a driving lane: {point}")
                candidates.append(nearest)
            paths = [(item, [item]) for item in candidates[0]
                     if item[0] == str(scene[f"{party}_approach_road_id"])]
            for choices in candidates[1:]:
                paths = [(item, history + [item]) for previous, history in paths for item in choices
                         if (item[0] == previous[0] and item[1] >= previous[1] - 0.2)
                         or (item[0] != previous[0] and _reachable(edges, previous[0], item[0]))]
            if not paths:
                raise ValueError(f"{scene_path}: {party} route lacks forward road/lane connectivity")
            chosen = min(paths, key=lambda pair: sum(item[2] for item in pair[1]))[1]
            if not any(roads[item[0]].get("junction") != "-1" for item in chosen[1:-1]):
                raise ValueError(f"{scene_path}: {party} route lacks a junction anchor")
            parties[party] = {"road_sequence": [item[0] for item in chosen],
                              "maximum_anchor_error_m": max(item[2] for item in chosen)}
        cases[scene["case_id"]] = parties
    return {"format": "c125714-diagnostic-opendrive-route-preflight-v1",
            "map_sha256": digest, "tolerance_m": tolerance_m, "cases": cases,
            "limitations": "Engineering OpenDRIVE screening only; requires live Native waypoint binding and reviewed legal context."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("map")
    parser.add_argument("scenes", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(preflight(args.map, args.scenes), indent=2) + "\n")


if __name__ == "__main__":
    main()
