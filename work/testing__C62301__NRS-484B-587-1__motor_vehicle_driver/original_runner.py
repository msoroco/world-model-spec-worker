"""Exact source-gated Native controlled-access entry/exit entrypoint."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from package_spec import AID, ACTOR, CAMERA_NAMES, CELL, LAW
from access import construct


def reviewed_site(path, case):
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    request = construct(site, case)
    if site.get("rate_hz") != 20 or site.get("duration_frames") != 900 or tuple(site.get("cameras", ())) != CAMERA_NAMES:
        raise ValueError("original 20 Hz four-view profile required")
    refs = site.get("source_refs")
    roles = {"map", "authority_determination", "public_highway_boundary", "official_device_inventory", "indicated_access_points", "target_crossing_point", "vehicle_pose", "driver_identity", "route_trajectory"}
    if not isinstance(refs, list) or not roles <= {item.get("role") for item in refs}:
        raise ValueError("complete separately sourced highway/lane/purpose facts required")
    for ref in refs:
        target = (path.parent / ref["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("reviewed source hash changed: " + ref.get("role", "unknown"))
    if site["map_sha256"] != next(ref["sha256"] for ref in refs if ref["role"] == "map"):
        raise ValueError("Native map source differs")
    site["reviewed_site_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return site, request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    case = config["selected_case_id"]
    if (config["assignment_id"], config["law_id"], config["cell_id"], config["actor"]) != (AID, LAW, CELL, ACTOR) or args.case not in (None, case):
        raise ValueError("exact selected controlled-access case differs")
    if args.check:
        print("exact controlled-access runner static check passed: " + case)
        return
    site_path = args.site or os.environ.get("C62301_REVIEWED_SITE")
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError("reviewed Native controlled-access site, host, port and output required")
    site, request = reviewed_site(site_path, case)
    from access_carla_adapter import CarlaAccessAdapter
    from access_capture import capture
    capture(CarlaAccessAdapter(args.host, args.port, site, request,
                                  config.get("control_profile", {})), site, case, args.output_dir)


if __name__ == "__main__":
    main()
