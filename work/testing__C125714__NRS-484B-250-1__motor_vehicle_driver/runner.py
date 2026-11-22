"""C125714 Native entrypoint; execution uses a source-reviewed local scene."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_control import validate_routes


def check_scene(scene):
    validate_routes(scene)
    if scene.get("capture_rate_hz") != 20 or not isinstance(scene.get("duration_s"), (int, float)):
        raise ValueError("20 Hz positive duration is required")
    if scene["duration_s"] <= 0 or round(scene["duration_s"] * 20) < 2:
        raise ValueError("Native capture needs at least two original frames")
    if type(scene.get("other_entered_first")) is not bool:
        raise ValueError("entry-order target must be explicit")
    if scene.get("ego_response_request", "yield") not in ("yield", "advance"):
        raise ValueError("ego response request must be yield or advance")
    if not scene.get("case_id") or not scene.get("reviewed_context_source") or not scene.get("reviewed_context_sha256"):
        raise ValueError("case identity and reviewed source binding required")
    return scene


def resolve_reviewed_source(scene, scene_path):
    """Bind the inspected packet to the scene file, independent of process cwd."""
    source = Path(scene["reviewed_context_source"])
    if not source.is_absolute():
        source = Path(scene_path).resolve().parent / source
    source = source.resolve()
    if hashlib.sha256(source.read_bytes()).hexdigest() != scene["reviewed_context_sha256"]:
        raise ValueError("reviewed context source hash differs from scene")
    reviewed = json.loads(source.read_text())
    if reviewed.get("crossing") != scene["crossing"]:
        raise ValueError("reviewed crossing differs from scene")
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default=str(Path(__file__).with_name("scene.json")))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene = check_scene(json.loads(Path(args.scene).read_text()))
    source = resolve_reviewed_source(scene, args.scene)
    from case_builder import config
    expected = config(scene)
    config_path = Path(args.scene).with_name("config.json")
    if not config_path.is_file() or json.loads(config_path.read_text()) != expected:
        raise ValueError("materialized exact config differs from reviewed scene")
    if args.check:
        print(json.dumps({"case_id": scene["case_id"], "static_construction_valid": True,
                          "native_started": False}))
    elif args.output_dir:
        from native_capture import run_native
        run_native({**scene, "reviewed_context_source": str(source)},
                   args.output_dir, args.host, args.port)
    else:
        parser.error("use --check or --output-dir")


if __name__ == "__main__":
    main()
