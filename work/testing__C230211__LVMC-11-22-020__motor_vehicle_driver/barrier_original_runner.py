"""One exact reviewed Native highway/barrier capture entrypoint."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from package_spec import AID, CAMERA_NAMES


def reviewed_site(path, case):
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if (site.get("source_kind") != "reviewed_original_native_site" or
            site.get("assignment_id") != AID or site.get("case_id") != case or
            site.get("cell_id") != "C230211" or
            site.get("city_highway_status") not in ("established", "unresolved")):
        raise ValueError("reviewed exact highway/barrier site identity missing")
    if not site.get("map_name") or not site.get("map_sha256") or \
            site.get("duration_frames") != 900 or site.get("rate_hz") != 20 or \
            tuple(site.get("cameras", ())) != CAMERA_NAMES:
        raise ValueError("Native map or 900-frame capture profile missing")
    refs = site.get("source_refs")
    required = {"map", "highway", "city_status", "barrier", "road_bounds",
                "surrounding_conditions"}
    if not isinstance(refs, list) or not required <= {ref.get("role") for ref in refs}:
        raise ValueError("reviewed Native site source classes missing")
    for ref in refs:
        target = (path.parent / ref["path"]).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file() or \
                hashlib.sha256(target.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError("reviewed Native site source hash changed: " + ref.get("role", "unknown"))
    if site.get("map_sha256") != next(ref["sha256"] for ref in refs if ref["role"] == "map"):
        raise ValueError("Native map source hash differs")
    from barrier_route import construct
    profile = case.removeprefix(AID + "__")
    if profile not in ("wide_clearance", "near_clearance"):
        raise ValueError("exact barrier case missing")
    route = construct(path, "wide" if profile == "wide_clearance" else "near")
    site["reviewed_site_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return site, route


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.is_file():
        raise ValueError("exact bundled config missing")
    config = json.loads(config_path.read_text())
    case = config["selected_case_id"]
    if args.case is not None and args.case != case:
        raise ValueError("selected exact case changed")
    if args.check:
        print("exact barrier runner static check passed: " + case)
        return
    site_path = args.site or os.environ.get("C230211_REVIEWED_SITE")
    if not site_path or not args.host or not args.port or args.output_dir is None:
        raise ValueError("reviewed Native site, host, port and output required")
    site, route = reviewed_site(site_path, case)
    from barrier_carla_adapter import CarlaBarrierAdapter
    from barrier_capture import capture
    adapter = CarlaBarrierAdapter(args.host, args.port, site, config.get("control_profile", {}))
    capture(adapter, site, route, case, args.output_dir)


if __name__ == "__main__":
    main()
