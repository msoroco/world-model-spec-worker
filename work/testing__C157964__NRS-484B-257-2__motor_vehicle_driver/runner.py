"""Exact case Native entrypoint for the officer-controlled exception."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from officer_scene import CASES


def check(root: Path) -> dict:
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    plan_path = root / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    if config.get("plan_sha256") != hashlib.sha256(plan_path.read_bytes()).hexdigest():
        raise ValueError("case plan changed after construction")
    case_id = config.get("selected_case_id")
    selected = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(selected) != 1 or config.get("case", {}).get("draft_variables") != \
            selected[0]["draft_variables"]:
        raise ValueError("exact officer case variables differ")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != \
            ("NRS-484B-257-2", "C157964", "motor_vehicle_driver"):
        raise ValueError("wrong frozen officer assignment identity")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45 or \
            config.get("frame_count") != 900:
        raise ValueError("wrong original capture time contract")
    cameras = config.get("cameras", [])
    if [row.get("name") for row in cameras] != \
            ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("wrong four camera views")
    if [(row.get("width"), row.get("height")) for row in cameras] != \
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError("wrong four camera dimensions")
    if set(config.get("supported_case_ids", [])) != {row["case_id"] for row in plan["cases"]}:
        raise ValueError("supported case inventory differs")
    if case_id.removeprefix(config["assignment_id"] + "__") not in \
            {row.suffix for row in CASES}:
        raise ValueError("unknown officer construction case")
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--adapter-module")
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    site = args.site or (Path(os.environ["C157964_SITE_PACKET"])
                         if os.environ.get("C157964_SITE_PACKET") else None)
    output = args.output_dir or args.output
    module_name = args.adapter_module or os.environ.get("C157964_NATIVE_ADAPTER_MODULE")
    if site is None or output is None or not module_name:
        raise ValueError("reviewed site, output and Native adapter module required")
    from officer_native_capture import capture
    adapter = importlib.import_module(module_name).create_adapter(
        config, args.host, args.port)
    print(json.dumps(capture(adapter, config, site, output), sort_keys=True))


if __name__ == "__main__":
    main()
