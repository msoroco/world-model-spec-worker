"""Exact selected bus-loading Native entrypoint."""

import argparse
import json
from pathlib import Path

from native.bus_scene import request, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    scene = request(config["zone_kind_requested"],
                    vehicle_class=config["vehicle_class_requested"],
                    emergency=config["emergency_requested"])
    if args.check:
        print(json.dumps(validate(scene), sort_keys=True))
        return
    if not args.output_dir:
        parser.error("fresh output directory required")
    from native.bus_capture import capture
    print(json.dumps(capture(config["zone_kind_requested"], args.output_dir,
                             args.host, args.port,
                             vehicle_class=config["vehicle_class_requested"],
                             emergency=config["emergency_requested"]), sort_keys=True))


if __name__ == "__main__":
    main()
