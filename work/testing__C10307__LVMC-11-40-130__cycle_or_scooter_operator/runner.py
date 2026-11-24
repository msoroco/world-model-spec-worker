"""Source-gated bicycle/rack construction and original Native acquisition.

The CPU check is offline. Native execution requires SHA-bound local scene and
asset inventories, a supplied endpoint, and full source readback.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_geometry import validate_geometry
from native_controller import exact_case_target


ASSIGNMENT = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator"
CASE = ASSIGNMENT + "__reference"
ROOT = Path(__file__).resolve().parent


def check() -> dict:
    config = json.loads((ROOT / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id"),
            config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            ASSIGNMENT, "LVMC-11-40-130", "C10307", "cycle_or_scooter_operator"):
        raise ValueError("materialized bicycle case identity mismatch")
    if case_id not in config.get("supported_case_ids", []) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("materialized bicycle case unsupported")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("reference capture clock or duration changed")
    cameras = config.get("cameras", [])
    if (len(cameras) != 4 or [c.get("name") for c in cameras] !=
            ["overview", "approach", "reference_corner", "driver_reference"] or
            [(c.get("width"), c.get("height")) for c in cameras] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]):
        raise ValueError("four-camera capture profile changed")
    geometry = validate_geometry(ROOT / "authored-alley.xodr")
    target = exact_case_target(ROOT / "case-plan.json", case_id)
    if target != config.get("requested_speed_mps"):
        raise ValueError("reference target differs from reviewed case")
    return {"case_id": case_id, "route": geometry["route_xy_m"],
            "target_speed_mps": target, "asset_inventory_verified": False,
            "municipal_jurisdiction_verified": False,
            "capture_complete": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    status = check()
    if args.check:
        print(json.dumps(status, sort_keys=True))
        return
    if not args.output_dir:
        parser.error("Native attempt requires --output-dir")
    from native_run import run_native
    config = json.loads((ROOT / "config.json").read_text())
    print(json.dumps(run_native(args.output_dir, args.host, args.port, config), sort_keys=True))


if __name__ == "__main__":
    main()
