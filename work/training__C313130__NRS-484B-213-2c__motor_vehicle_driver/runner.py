"""Exact tunnel approach Native capture entrypoint; CARLA is imported lazily."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / "config.json").read_text())
    assignment = json.loads((bundle / "assignment-source.json").read_text())
    case = config.get("selected_case_id")
    if (case not in config.get("supported_case_ids", []) or
            case not in (assignment["assignment_id"] + "__probe_1",
                         assignment["assignment_id"] + "__probe_2") or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-213-2c", "C313130", "motor_vehicle_driver") or
            (config.get("rate_hz"), config.get("duration_frames")) != (20, 600)):
        raise ValueError("Exact tunnel identity or duration changed")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("road_sha256", "road.xodr")):
        if config.get(key) != sha(bundle / name):
            raise ValueError("Changed source: " + name)
    lanes = ET.parse(bundle / "road.xodr").getroot().findall(".//laneSection/*/lane")
    if not {"-1", "0", "1"}.issubset({lane.get("id") for lane in lanes}):
        raise ValueError("Original two-way tunnel request changed")
    cameras = config.get("cameras", [])
    if [item.get("name") for item in cameras] != ["overview", "approach", "reference_corner", "driver_reference"]:
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
    from native_capture import run
    run(args.bundle, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
