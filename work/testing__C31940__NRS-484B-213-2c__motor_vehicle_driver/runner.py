"""Exact reviewed-source CARLA entrypoint for NRS 484B.213(2)(c)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_capture import capture
from native_scene import ASSIGNMENT, validate
from source_bind import bind


def run(client, attempt, *, carla_module=None):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    if config.get("assignment_id") != ASSIGNMENT:
        raise ValueError("selected assignment mismatch")
    case_id = config["selected_case_id"]
    packet_path = attempt / config["reviewed_packet"]
    source_root = attempt / config["reviewed_source_root"]
    packet = validate(json.loads(packet_path.read_text(encoding="utf-8")), case_id)
    bound = bind(packet, source_root)
    if not bound:
        raise ValueError("no original source bindings")
    return capture(client, packet, case_id, source_root, attempt,
                   carla_module=carla_module)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"entrypoint": "runner.py", "assignment_id": ASSIGNMENT,
                          "reviewed_original_sources_required": True}, sort_keys=True))
        return
    if not args.host or args.port is None or args.output_dir is None:
        parser.error("--host, --port and --output-dir required")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    print(json.dumps(run(client, args.output_dir, carla_module=carla), sort_keys=True))


if __name__ == "__main__":
    main()
