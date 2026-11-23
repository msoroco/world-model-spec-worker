"""Canonical draft entrypoint for the C24811 exact Native package.

The config deliberately leaves the Native occluder blueprint and placement
unselected until source review. A capture refuses to run without them.
"""

import argparse
import json
from pathlib import Path

from native_runner import capture, check
from saved_finalizer import finalize_saved


ROOT = Path(__file__).resolve().parent


def validate_config():
    config = json.loads((ROOT/"config.json").read_text())
    case_ids = [case["case_id"] for case in json.loads((ROOT/"case-plan.json").read_text())["cases"]]
    if (config.get("assignment_id") !=
            "testing__C24811__NRS-484B-250-4__motor_vehicle_driver" or
            config.get("cell_id") != "C24811" or
            config.get("law_id") != "NRS-484B-250-4" or
            config.get("supported_case_ids") != case_ids or
            config.get("selected_case_id") not in case_ids or
            config.get("rate_hz") != 20 or
            config.get("frames") != config.get("duration_s", 0)*20):
        raise ValueError("Exact C24811 materialized configuration required")
    check()
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = validate_config()
    if args.check:
        print(json.dumps({"config_valid":True,"site_routes_cameras":check(),
                          "native_capture_verified":False},indent=2))
    elif args.attempt:
        if not args.output:
            parser.error("--output required with --attempt")
        finalize_saved(args.attempt,args.output)
    elif args.output_dir:
        occluder = config["occluder"]
        placement = occluder.get("placement")
        if not occluder.get("blueprint_id") or not isinstance(placement,dict):
            raise ValueError("Source-reviewed Native occluder blueprint and placement required")
        state = config.get("operative_signal_state")
        capture(argparse.Namespace(case_id=config["selected_case_id"],
            operative_state=state,occluder_blueprint=occluder["blueprint_id"],
            occluder_x=placement["x"],occluder_y=placement["y"],
            occluder_z=placement["z"],occluder_yaw=placement["yaw"],
            output_dir=args.output_dir,host=args.host,port=args.port))
    else:
        parser.error("--check, --output-dir, or --attempt with --output required")


if __name__ == "__main__":
    main()
