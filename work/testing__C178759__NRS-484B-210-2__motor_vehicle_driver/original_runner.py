"""Exact source-gated original Native right-pass entrypoint."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from package_spec import AID, ACTOR, CAMERA_NAMES, CELL, LAW
from right_pass import construct


def reviewed_site(path, case):
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    if site.get("reviewed_original_native_site") is not True or \
            site.get("source_kind") != "original_native_map_geometry" or \
            site.get("assignment_id") != AID or site.get("case_id") != case:
        raise ValueError("reviewed exact Native right-pass site required")
    if not site.get("map_name") or not site.get("map_sha256") or \
            site.get("duration_frames") != 900 or site.get("rate_hz") != 20 or \
            tuple(site.get("cameras", ())) != CAMERA_NAMES:
        raise ValueError("source map and four-view capture profile required")
    refs = site.get("source_refs")
    roles = {"map", "paved_boundary", "right_lane", "actor_poses", "surrounding_traffic"}
    if not isinstance(refs, list) or not roles <= {r.get("role") for r in refs}:
        raise ValueError("reviewed right-pass source classes missing")
    for ref in refs:
        target = (path.parent / ref["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or \
                hashlib.sha256(target.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("reviewed source hash changed: " + ref.get("role", "unknown"))
    if site["map_sha256"] != next(r["sha256"] for r in refs if r["role"] == "map"):
        raise ValueError("Native map source differs")
    variant = case.removeprefix(AID + "__")
    request = construct(site, variant)
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
    if (config["assignment_id"], config["law_id"], config["cell_id"], config["actor"]) != \
            (AID, LAW, CELL, ACTOR) or args.case not in (None, case):
        raise ValueError("exact selected right-pass case differs")
    if args.check:
        print("exact right-pass runner static check passed: " + case)
        return
    site_path = args.site or os.environ.get("C178759_REVIEWED_SITE")
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError("reviewed Native site, host, port and output required")
    site, request = reviewed_site(site_path, case)
    from right_pass_carla_adapter import CarlaRightPassAdapter
    from right_pass_capture import capture
    capture(CarlaRightPassAdapter(args.host, args.port, site, request,
                                  config.get("control_profile", {})),
            site, case, args.output_dir)


if __name__ == "__main__":
    main()
