"""C126120 Native entrypoint; a reviewed local scene is required."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from uturn_control import validate_scene


ASSIGNMENT = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver"


def check_scene(scene):
    validate_scene(scene)
    if not scene.get("case_id", "").startswith(ASSIGNMENT + "__"):
        raise ValueError("case ID differs from exact assignment")
    if scene.get("capture_rate_hz") != 20 or not isinstance(scene.get("duration_s"), (int,float)):
        raise ValueError("20 Hz Native duration required")
    if scene["duration_s"] <= 0 or round(scene["duration_s"]*20) < 3:
        raise ValueError("Native capture needs three or more original frames")
    if not scene.get("reviewed_context_source") or not scene.get("reviewed_context_sha256"):
        raise ValueError("reviewed median source binding required")
    if not scene.get("authority_review_source"):
        raise ValueError("authority review source required")
    return scene


def _resolve(scene, scene_path):
    scene = dict(scene)
    for key in ("reviewed_context_source", "authority_review_source"):
        source = Path(scene[key])
        if not source.is_absolute():
            source = scene_path.resolve().parent / source
        scene[key] = str(source)
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene_path = Path(args.scene)
    scene = check_scene(_resolve(json.loads(scene_path.read_text()), scene_path))
    source = Path(scene["reviewed_context_source"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != scene["reviewed_context_sha256"]:
        raise ValueError("reviewed median source hash differs from scene")
    reviewed = json.loads(source.read_text())
    if reviewed.get("context") != scene["context"]:
        raise ValueError("reviewed median geometry differs from scene")
    authority = Path(scene["authority_review_source"])
    if hashlib.sha256(authority.read_bytes()).hexdigest() != scene["context"]["authority_review_source_sha256"]:
        raise ValueError("authority review source hash differs from scene")
    from case_builder import config
    expected = config(scene)
    config_path = scene_path.with_name("config.json")
    if not config_path.is_file() or json.loads(config_path.read_text()) != expected:
        raise ValueError("exact config differs from reviewed scene")
    if args.check:
        print(json.dumps({"case_id":scene["case_id"],"static_construction_valid":True,
                          "native_started":False}))
    elif args.output_dir:
        from native_capture import run_native
        run_native(scene, args.output_dir, args.host, args.port)
    else:
        parser.error("use --check or --output-dir")


if __name__ == "__main__":
    main()
