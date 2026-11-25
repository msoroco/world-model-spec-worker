"""Exact C111610 crosswalk Native entrypoint for one selected scene."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    scene = json.loads((root / "scene.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-283-1a", "C111610", "motor_vehicle_driver"):
        raise ValueError("wrong exact crosswalk identity")
    if case_id != scene.get("case_id") or case_id not in config.get("supported_case_ids", []):
        raise ValueError("selected exact crosswalk case differs")
    if hashlib.sha256((root / "scene.json").read_bytes()).hexdigest() != config.get("scene_sha256"):
        raise ValueError("selected scene source changed")
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("frame_count")) != (20, 30, 600):
        raise ValueError("crosswalk capture timebase changed")
    if [item.get("name") for item in config.get("cameras", [])] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four original crosswalk cameras required")
    if scene.get("turn_direction") != "left" or scene.get("rate_hz") != 20:
        raise ValueError("fixed left-turn scene changed")
    return case_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    check()
    if args.check:
        return 0
    if args.output_dir is None:
        raise ValueError("original Native output directory required")
    source_root = Path(os.environ.get("C111610_SITE_ROOT", str(ROOT))).resolve()
    site, exception = source_root / "site.json", source_root / "exception.json"
    if not site.is_file() or not exception.is_file():
        raise ValueError("reviewed original site and exception packets required")
    from live_entrypoint import run
    run(host=args.host, port=args.port, scene=ROOT / "scene.json", site=site,
        exception=exception, output=args.output_dir / "capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
