"""Launch one source-reviewed exact Native stop case; --check needs no CARLA."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from stop_model import ASSIGNMENT, BY_NAME, LAW, reviewed_scene


def checked_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id", "")
    if (config.get("assignment_id") != ASSIGNMENT
            or config.get("law_id") != LAW
            or config.get("cell_id") != "C150640"
            or config.get("actor") != "motor_vehicle_driver"
            or config.get("rate_hz") != 20
            or config.get("duration_s") != 45
            or config.get("engineering", {}).get("stop_trigger_frame") not in (170, 200)
            or case_id.removeprefix(ASSIGNMENT + "__") not in BY_NAME):
        raise ValueError("frozen one-way stop capture contract differs")
    cameras = config.get("cameras", [])
    if [(camera.get("name"), camera.get("width"), camera.get("height")) for camera in cameras] != [
        ("overview", 1920, 1080), ("approach", 1280, 720),
        ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("four-camera capture profile differs")
    return config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    config = checked_config(Path(__file__).resolve().parent / "config.json")
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"],
                          "source_gated_capture_contract_checked": True}))
        return 0
    if args.output_dir is None:
        parser.error("--output-dir required")
    source = os.environ.get("C150640_STOP_REVIEWED_SCENE")
    if not source:
        raise ValueError("C150640_STOP_REVIEWED_SCENE original reviewed packet required")
    packet = Path(source).resolve()
    scene = reviewed_scene(packet, config["selected_case_id"])
    from native_stop import run_native
    run_native(config, scene, packet, args.output_dir, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
