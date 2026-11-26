"""Exact median-opening timing construction gate; Native implementation is source-bound."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

ASSIGNMENT = "testing__C125745__NRS-484B-250-2__motor_vehicle_driver"
SUFFIXES = ("entry_below", "entry_inside", "entry_above")
REQUIRED_SITE = ("map_source_sha256", "intersection_source_sha256",
                 "highway_source_sha256", "device_source_sha256",
                 "intersection_polygon_xy_m", "ego_road_id", "other_road_id",
                 "ego_spawn_transform", "other_spawn_transform",
                 "ego_route_waypoints", "other_route_waypoints",
                 "ego_actor_id", "other_actor_id",
                 "device_authority_review", "different_highways_review",
                 "left_right_priority_review")


def check(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    case = config.get("selected_case_id")
    if case not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("exact median-opening timing case mismatch")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-250-2", "C125745", "motor_vehicle_driver"):
        raise ValueError("frozen law/cell/actor mismatch")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("original capture clock changed")
    if [x.get("name") for x in config.get("cameras", [])] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four original camera views required")
    return config


def reviewed_site(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed site hash mismatch")
    site = json.loads(raw)
    if any(not site.get(key) for key in REQUIRED_SITE):
        raise ValueError("median-opening geometry or review source absent")
    if site["ego_road_id"] == site["other_road_id"]:
        raise ValueError("different highway identities required")
    if site["device_authority_review"] not in ("official", "non_official", "unresolved"):
        raise ValueError("device authority review invalid")
    return site


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--adapter-module")
    parser.add_argument("--host")
    parser.add_argument("--port")
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    if args.site is None or not args.site_sha256:
        raise ValueError("source-hashed reviewed median-opening site required")
    if args.output_dir is None:
        raise ValueError("materialized exact output directory required")
    module = args.adapter_module or os.environ.get("C125745_NATIVE_ADAPTER_MODULE")
    if not module:
        raise ValueError("local CARLA adapter module required")
    site = reviewed_site(args.site, args.site_sha256)
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(
        config, args.host or os.environ.get("CARLA_HOST"),
        args.port or os.environ.get("CARLA_PORT"))
    print(json.dumps(capture(adapter, config, site, args.site,
                             args.site_sha256, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
