"""Exact one-way parking entry point; CARLA is imported only for capture."""

import argparse
import json
import os
from pathlib import Path

from oneway_site import ASSIGNMENT, load_site


ROOT = Path(__file__).resolve().parent


def selected_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if (cfg.get("assignment_id") != ASSIGNMENT or cfg.get("law_id") != "NRS-484B-497"
            or cfg.get("cell_id") != "C229439" or cfg.get("actor") != "vehicle_parker"
            or cfg.get("rate_hz") != 20 or cfg.get("duration_s") != 20
            or cfg.get("selected_case_id") not in cfg.get("supported_case_ids", [])):
        raise ValueError("exact one-way parking identity or 20 Hz capture contract differs")
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
                          "reviewed_site_required_for_native": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    source_root = os.environ.get("C229439_ONEWAY_SITE_ROOT")
    if not source_root:
        raise ValueError("C229439_ONEWAY_SITE_ROOT reviewed source directory required")
    site_path = Path(source_root) / (cfg["selected_case_id"].split("__")[-1] + ".json")
    site, records = load_site(site_path, cfg["selected_case_id"])
    from native_oneway import run_native
    run_native(cfg, site, records, site_path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
