"""C147332 12a entrypoint; --check is entirely offline."""
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
        raise ValueError("road source escapes exact bundle")
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
    packet = os.environ.get("C147332_GREEN_REVIEWED_SOURCE_PACKET")
    if not packet:
        raise ValueError("C147332_GREEN_REVIEWED_SOURCE_PACKET required before Native dispatch")
    from source_review import validate
    site = validate(packet, source_root=Path(packet).resolve().parent)
    expected = {signal["governed_lane_id"] for signal in scene["signals"]
                if signal["display"] == "down_green_arrow"}
    if set(site["governed_lane_ids"]) != expected:
        raise ValueError("reviewed green-arrow lane association differs from exact case")
    from native_capture import run_native
    run_native(scene, road, site, args.output_dir, args.host, args.port, packet)


if __name__ == "__main__":
    main()
