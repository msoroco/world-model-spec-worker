"""CPU inventory of an OpenDRIVE source before median-opening route review.

This reports source geometry and declared signals. It does not establish public
access, official-device status, a statutory intersection, or legal priority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def inventory(path):
    data = Path(path).read_bytes()
    root = ET.fromstring(data)
    if root.tag != "OpenDRIVE":
        raise ValueError("not an OpenDRIVE source")
    roads = []
    for road in root.findall("road"):
        plan = road.find("planView")
        if plan is None:
            raise ValueError("OpenDRIVE road lacks planView")
        geometries = []
        for item in plan.findall("geometry"):
            values = {key: float(item.attrib[key]) for key in ("s", "x", "y", "hdg", "length")}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError("non-finite OpenDRIVE geometry")
            values["primitive"] = next(iter(item), ET.Element("missing")).tag
            geometries.append(values)
        if not geometries:
            raise ValueError("OpenDRIVE road lacks geometry")
        signals = [{key: signal.get(key) for key in ("id", "name", "type", "subtype",
                                                    "s", "t", "orientation")}
                   for signal in road.findall("./signals/signal")]
        lanes = []
        for section in road.findall("./lanes/laneSection"):
            for side in ("left", "center", "right"):
                for lane in section.findall("./" + side + "/lane"):
                    lanes.append({"section_s": section.get("s"), "side": side,
                                  "id": lane.get("id"), "type": lane.get("type")})
        roads.append({"id": road.get("id"), "name": road.get("name"),
                      "length_m": road.get("length"), "junction": road.get("junction"),
                      "geometry": geometries, "lanes": lanes, "signals": signals})
    junctions = []
    for junction in root.findall("junction"):
        junctions.append({"id": junction.get("id"), "name": junction.get("name"),
                          "connections": [{key: connection.get(key) for key in
                                           ("id", "incomingRoad", "connectingRoad", "contactPoint")}
                                          for connection in junction.findall("connection")]})
    if len({road["id"] for road in roads}) != len(roads):
        raise ValueError("duplicate OpenDRIVE road ID")
    return {"format": "c125714-opendrive-inventory", "source_sha256": hashlib.sha256(data).hexdigest(),
            "roads": roads, "junctions": junctions,
            "limitations": ["Declared signal XML does not prove complete official-device inventory.",
                            "Road geometry does not prove public highway access or statutory crossing bounds."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(inventory(args.source), indent=2) + "\n")


if __name__ == "__main__":
    main()
