"""Exact first-case Native entrypoint for NRS 484B.400(3)."""

import argparse
import json
import os
from pathlib import Path

from turn_native_plan import ASSIGNMENT, prepare
from turn_native_capture import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site-source")
    parser.add_argument("--site-sha256")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    expected = ASSIGNMENT + "__centerline_approach_left_curb_departure"
    if (config.get("selected_case_id") != expected or config.get("law_id") != "NRS-484B-400-3" or
            config.get("cell_id") != "C228670" or config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("frames") != 160 or
            config.get("duration_s") != 8):
        raise ValueError("Exact turn construction identity or duration changed")
    if args.check:
        if args.output_dir or args.site_source or args.site_sha256:
            raise ValueError("Offline check cannot create Native output")
        return
    if not args.output_dir:
        parser.error("--output-dir required")
    source = args.site_source or os.environ.get("TURN_ROUTE_SITE_SOURCE")
    digest = args.site_sha256 or os.environ.get("TURN_ROUTE_SITE_SHA256")
    if not source or not digest:
        raise ValueError("Native capture requires exact route site source and SHA-256")
    plan = prepare(expected, source, digest)
    engineering = config["engineering"]
    for key in ("spawn_height_offset_m", "target_speed_mps", "overview_mount_z_m"):
        plan[key] = float(engineering[key])
    run(plan, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
