"""Exact C147332 Native entrypoint; --check never imports CARLA."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from native_construction import check_scene


def check(path):
    path = Path(path).resolve()
    scene = json.loads(path.read_text())
    road = (path.parent / scene["map_source"]).resolve()
    if road.parent != path.parent:
        raise ValueError("map source escapes exact bundle")
    return scene, road, check_scene(scene, road)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="scene.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene, road, static = check(args.scene)
    if args.check:
        print(json.dumps(static))
        return
    if not args.output_dir:
        parser.error("use --check or --output-dir")
    packet_path = os.environ.get("C147332_REVIEWED_SOURCE_PACKET")
    if not packet_path:
        raise ValueError("C147332_REVIEWED_SOURCE_PACKET required before Native dispatch")
    from source_review import validate as validate_site
    site = validate_site(packet_path, source_root=Path(packet_path).resolve().parent)
    from native_capture import run_native
    run_native(scene, road, site, args.output_dir, args.host, args.port, packet_path)


if __name__ == "__main__":
    main()
