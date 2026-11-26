"""Exact posted-speed construction entrypoint, gated on a reviewed site."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path

from posted_site import CASES, load


ASSIGNMENT = "testing__C136559__NRS-484B-600-1c__motor_vehicle_driver"


def check(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    exact = config.get("selected_case_id")
    suffix = exact.rsplit("__", 1)[-1] if isinstance(exact, str) else None
    if suffix not in CASES or exact != ASSIGNMENT + "__" + suffix:
        raise ValueError("exact posted-speed case mismatch")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            ASSIGNMENT, "NRS-484B-600-1c", "C136559", "motor_vehicle_driver"):
        raise ValueError("posted-speed scope mismatch")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("original 20 Hz capture contract changed")
    if [camera.get("name") for camera in config.get("cameras", [])] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four-view capture contract changed")
    if config.get("case", {}).get("case_id") != exact:
        raise ValueError("selected case and construction disagree")
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--adapter-module")
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    site = args.site or (Path(os.environ["C136559_POSTED_SITE"]) if os.environ.get("C136559_POSTED_SITE") else None)
    site_sha = args.site_sha256 or os.environ.get("C136559_POSTED_SITE_SHA256")
    module = args.adapter_module or os.environ.get("C136559_NATIVE_ADAPTER_MODULE") or "native_adapter"
    if site is None or not site_sha or args.output_dir is None:
        raise ValueError("reviewed posted-speed site, hash and output directory required")
    packet = load(site, site_sha, config["selected_case_id"])
    variables = config["case"]["draft_variables"]
    if variables["travel_direction"] not in packet["travel_lanes"]:
        raise ValueError("selected direction lacks reviewed lane")
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(config, args.host, args.port, args.output_dir)
    print(json.dumps(capture(adapter, config, site, site_sha, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
