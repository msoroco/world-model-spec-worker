"""Exact bridge and viaduct Native entrypoint; CARLA imports on execution."""

import argparse
import hashlib
import json
from pathlib import Path

from structure_variant import request, validate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / "config.json").read_text())
    assignment = json.loads((bundle / "assignment-source.json").read_text())
    kind = config.get("structure_kind")
    side = config.get("requested_lateral_target")
    if kind not in ("bridge", "viaduct") or side not in ("right", "left"):
        raise ValueError("Unknown statutory structure case")
    case = assignment["assignment_id"] + "__" + kind + "_" + side
    if (config.get("assignment_id") != assignment["assignment_id"] or
            config.get("selected_case_id") != case or
            case not in config.get("supported_case_ids", []) or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-213-2c", "C313130", "motor_vehicle_driver") or
            (config.get("rate_hz"), config.get("duration_frames")) != (20, 600) or
            (config.get("candidate_id"), config.get("controller_gain")) not in
            (("primary", 1.5), ("fallback1", 2.0)) or
            config.get("requested_left_side") is not (side == "left")):
        raise ValueError("Exact structure identity, target or duration changed")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("road_sha256", "road.xodr")):
        if config.get(key) != digest(bundle / name):
            raise ValueError("Changed source: " + name)
    requested = request(kind, side)
    validate(requested)
    if (bundle / "road.xodr").read_text() != requested["road_opendrive"]:
        raise ValueError("Fixed same-cell raised road differs")
    if (not isinstance(config.get("support_blueprint"), str) or
            not config["support_blueprint"].startswith("static.prop.") or
            config.get("tunnel_blueprint") != "static.prop.tunnel" or
            config.get("occluder_blueprint") != "static.prop.hedge"):
        raise ValueError("Installed Native structure asset request missing")
    cameras = config.get("cameras", [])
    if [item.get("name") for item in cameras] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four exact camera names/order missing")
    if any(item.get("fps") != 20 or item.get("width") !=
           (1920 if item["name"] == "overview" else 1280) or item.get("height") !=
           (1080 if item["name"] == "overview" else 720) for item in cameras):
        raise ValueError("Exact camera profile changed")
    return {"case_id": case, "candidate_id": config["candidate_id"],
            "structure_kind_requested": kind, "frames": 600,
            "native_executed": False, "legal_verdict": None}


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
    from structure_capture import run
    run(args.bundle, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
