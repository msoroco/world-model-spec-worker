"""Exact parking case entrypoint; CARLA is imported only for explicit capture."""

import argparse
import json
import os
from pathlib import Path

from comparison_audit import CASES
from parking_place import ASSIGNMENT, construct
from site_review import reviewed_site

ROOT = Path(__file__).resolve().parent


def config():
    value = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    suffix = value.get("selected_case_id", "").removeprefix(ASSIGNMENT + "__")
    if (value.get("assignment_id") != ASSIGNMENT or suffix not in CASES
            or value.get("law_id") != "NRS-484B-500" or value.get("cell_id") != "C229439"
            or value.get("actor") != "vehicle_parker" or value.get("rate_hz") != 20
            or value.get("duration_s") != 20):
        raise ValueError("frozen parking case or capture contract differs")
    return value


def source_site(value):
    directory = os.environ.get("C229439_SITE_ROOT")
    if not directory:
        raise ValueError("C229439_SITE_ROOT reviewed site directory required")
    path = Path(directory) / (value["selected_case_id"].split("__")[-1] + ".json")
    reviewed_site(path, value["selected_case_id"])
    site = json.loads(path.read_text(encoding="utf-8"))
    suffix = value["selected_case_id"].split("__")[-1]
    conduct, footprint, context = CASES[suffix]
    if site.get("requested_conduct") != conduct or site.get("place_context_for_review") != context:
        raise ValueError("reviewed site does not bind requested conduct and place context")
    placement = construct(path, suffix)
    if placement["wholly_within_designated_place"] != (footprint == "inside"):
        raise ValueError("reviewed site differs from designated footprint intent")
    return path, site, placement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    value = config()
    if args.check:
        print(json.dumps({"case_id": value["selected_case_id"],
                          "capture_contract_checked": True,
                          "reviewed_site_required_for_native": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    path, site, placement = source_site(value)
    from native_parking import run_native
    run_native(value, site, path, placement, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
