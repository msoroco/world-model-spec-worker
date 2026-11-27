"""Exact one-way tunnel Native entrypoint, with CARLA imported only on execution."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / "config.json").read_text())
    assignment = json.loads((bundle / "assignment-source.json").read_text())
    case = config.get("selected_case_id")
    if (case not in config.get("supported_case_ids", []) or
            case not in (assignment["assignment_id"] + "__one_way_right",
                         assignment["assignment_id"] + "__one_way_left") or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-213-2c", "C313130", "motor_vehicle_driver") or
            (config.get("rate_hz"), config.get("duration_frames")) != (20, 600) or
            (config.get("candidate_id"), config.get("controller_gain")) not in
            (("primary", 1.5), ("fallback1", 2.0)) or
            config.get("requested_left_side") is not case.endswith("__one_way_left")):
        raise ValueError("Exact one-way tunnel identity, target or duration changed")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("road_sha256", "road.xodr")):
        if config.get(key) != digest(bundle / name):
            raise ValueError("Changed source: " + name)
    lanes = ET.parse(bundle / "road.xodr").getroot().findall(".//laneSection/*/lane")
    actual = {int(lane.get("id")): lane.get("type") for lane in lanes}
    if actual != {0: "none", -1: "driving", -2: "driving"}:
        raise ValueError("Original one-way tunnel road request changed")
    cameras = config.get("cameras", [])
    if [item.get("name") for item in cameras] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four exact camera names/order missing")
    if any(item.get("fps") != 20 or item.get("width") !=
           (1920 if item["name"] == "overview" else 1280) or item.get("height") !=
           (1080 if item["name"] == "overview" else 720) for item in cameras):
        raise ValueError("Exact camera profile changed")
    return {"case_id": case, "candidate_id": config["candidate_id"],
            "frames": 600, "native_executed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--bundle", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    checked = check(args.bundle)
    if args.check:
        print(json.dumps(checked))
        return
    if not args.output_dir or not args.host or not args.port:
        parser.error("Native output, host and port required")
    from one_way_capture import run
    run(args.bundle, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
