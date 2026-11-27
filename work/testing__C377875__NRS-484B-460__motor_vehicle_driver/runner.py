"""Exact source-gated NRS 484B.460 Native angle-parking entry point."""
import argparse
import json
import os
from pathlib import Path

from angle_site import ASSIGNMENT, load_site

ROOT = Path(__file__).resolve().parent


def selected_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if (cfg.get("assignment_id") != ASSIGNMENT or cfg.get("law_id") != "NRS-484B-460"
            or cfg.get("cell_id") != "C377875" or cfg.get("actor") != "motor_vehicle_driver"
            or cfg.get("rate_hz") != 20 or cfg.get("duration_s") != 30
            or cfg.get("selected_case_id") not in cfg.get("supported_case_ids", [])):
        raise ValueError("exact angle-parking identity or 20 Hz capture contract differs")
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    cfg = selected_config()
    if args.check:
        print(json.dumps({"case_id": cfg["selected_case_id"],
                          "capture_contract_checked": True,
                          "reviewed_original_site_required_for_native": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    root = os.environ.get("C377875_ANGLE_SITE_ROOT")
    if not root:
        raise ValueError("C377875_ANGLE_SITE_ROOT reviewed source directory required")
    name = cfg["selected_case_id"].split("__")[-1]
    site_path = Path(root) / (name + ".json")
    site, records = load_site(site_path, cfg["selected_case_id"])
    request = cfg["case"]
    if site["requested_activity"] != request["activity_request"] or site["requested_orientation"] != request["orientation_request"]:
        raise ValueError("reviewed site differs from exact case construction")
    from angle_native import run_native
    run_native(cfg, site, records, site_path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
