"""Original CARLA entrypoint for one reviewed signal case."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from construction import CASE_PROFILES, CAMERAS
from signal_capture import capture


def reviewed_scene(path, case):
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding="utf-8"))
    if scene.get("source_kind") != "reviewed_original_native_scene" or \
            scene.get("case_id") != case or scene.get("cell_id") != "C158196" or \
            scene.get("actor") != "motor_vehicle_driver":
        raise ValueError("reviewed exact Native scene identity missing")
    if scene.get("map_name") is None or len(scene.get("map_sha256", "")) != 64:
        raise ValueError("reviewed OpenDRIVE map identity missing")
    if not isinstance(scene.get("intersection_polygon_xy"), list) or \
            len(scene["intersection_polygon_xy"]) < 3:
        raise ValueError("surveyed intersection polygon missing")
    if not scene.get("route_native_lanes") or not isinstance(scene.get("approach_yaw_deg"), (int, float)):
        raise ValueError("reviewed route Native lanes or heading missing")
    if scene.get("duration_frames") != 900 or scene.get("rate_hz") != 20 or \
            tuple(scene.get("cameras", ())) != CAMERAS:
        raise ValueError("original capture profile changed")
    refs = ("intersection_polygon_source", "route_connectivity_source",
            "device_route_binding_source", "official_device_source")
    if case == "yellow_non_alone":
        refs += ("companion_device_source",)
    if case == "red_other_route":
        refs += ("other_route_device_source",)
    for label in refs:
        ref = scene.get(label)
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            raise ValueError("missing reviewed source: " + label)
        target = (path.parent / ref["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or \
                hashlib.sha256(target.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("reviewed source seal mismatch: " + label)
    if scene["intersection_polygon_source"]["sha256"] != scene["intersection_polygon_sha256"] or \
            scene["route_connectivity_source"]["sha256"] != scene["route_connectivity_sha256"] or \
            scene["official_device_source"]["sha256"] != scene["official_device_sha256"] or \
            scene["device_route_binding_source"]["sha256"] != scene["signal_route_binding_sha256"]:
        raise ValueError("reviewed scene/source hashes disagree")
    if case == "yellow_non_alone" and scene["companion_device_source"]["sha256"] != \
            scene["companion_device_sha256"]:
        raise ValueError("companion source hash differs")
    if case == "red_other_route" and (scene["other_route_device_source"]["sha256"] !=
                                      scene.get("other_route_device_sha256") or
                                      not scene.get("other_route_native_lanes")):
        raise ValueError("other-route source binding differs")
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", choices=tuple(CASE_PROFILES))
    parser.add_argument("--scene", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--adapter-module")
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        selected = config["selected_case_id"].removeprefix(config["assignment_id"] + "__")
        if args.case is not None and args.case != selected:
            raise ValueError("selected exact case differs from bundled configuration")
        args.case = selected
    if args.case not in CASE_PROFILES:
        raise ValueError("exact bundled signal case missing")
    if args.check:
        print("exact signal runner static check passed: " + args.case)
        return
    if not args.host or not args.port or args.output_dir is None:
        raise ValueError("Native host, port and owned output directory required")
    packet = args.scene or os.environ.get("C158196_REVIEWED_SCENE")
    if not packet:
        raise ValueError("reviewed Native scene packet required")
    scene = reviewed_scene(packet, args.case)
    name = args.adapter_module or os.environ.get("C158196_NATIVE_ADAPTER_MODULE") or \
        "signal_carla_adapter"
    adapter = importlib.import_module(name).create_adapter(args.host, args.port, scene)
    capture(adapter, scene, args.case, args.output_dir)


if __name__ == "__main__":
    main()
