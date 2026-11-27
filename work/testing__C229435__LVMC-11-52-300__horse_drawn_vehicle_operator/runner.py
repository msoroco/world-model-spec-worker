"""Selected nighttime parking capture entrypoint.

An original reviewed site packet is mandatory for Native execution. The CPU
check validates the selected request and never substitutes a synthetic site.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from night_parking_construction import plan_case, validate_site

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C229435__LVMC-11-52-300__horse_drawn_vehicle_operator"


def selected_config():
    value = json.loads((ROOT / "config.json").read_text())
    if (value.get("assignment_id") != ASSIGNMENT
            or value.get("law_id") != "LVMC-11-52-300"
            or value.get("cell_id") != "C229435"
            or value.get("actor") != "horse_drawn_vehicle_operator"
            or value.get("rate_hz") != 20
            or value.get("duration_s") != 1805.05
            or value.get("capture_queue_capacity") not in (4, 16)
            or value.get("selected_case_id") not in value.get("supported_case_ids", [])):
        raise ValueError("selected nighttime parking contract differs")
    request = value.get("case", {})
    if request.get("case_id") != value["selected_case_id"]:
        raise ValueError("selected case request differs")
    if request.get("design", {}).get("other_vehicle") != "present; original body and state required":
        raise ValueError("second vehicle construction required")
    return value


def reviewed_plan(value):
    root = os.environ.get("C229435_SITE_ROOT")
    if not root:
        raise ValueError("C229435_SITE_ROOT reviewed original site directory required")
    root = Path(root).resolve()
    packet_path = root / (value["selected_case_id"].rsplit("__", 1)[-1] + ".json")
    packet = validate_site(packet_path, root)
    return packet_path, packet, plan_case(value["case"], packet)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    value = selected_config()
    if args.check:
        print(json.dumps({"case_id": value["selected_case_id"],
                          "capture_contract_checked": True,
                          "reviewed_original_site_required_for_native": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    packet_path, packet, construction = reviewed_plan(value)
    from night_parking_native import run_native
    run_native(value, packet_path, packet, construction, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
