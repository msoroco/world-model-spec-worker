"""Canonical draft entrypoint for the C24811 exact Native package.

Native capture selects an available vehicle blueprint only after checking its
realized footprint against both sight rays and the two travel corridors.
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
    site = json.loads((ROOT/"blind-site-candidate.json").read_text())
    if (config.get("assignment_id") !=
            "testing__C24811__NRS-484B-250-4__motor_vehicle_driver" or
            config.get("cell_id") != "C24811" or
            config.get("law_id") != "NRS-484B-250-4" or
            config.get("supported_case_ids") != case_ids or
            config.get("selected_case_id") not in case_ids or
            config.get("rate_hz") != 20 or
            config.get("frames") != config.get("duration_s", 0)*20):
        raise ValueError("Exact C24811 materialized configuration required")
    occluder = config.get("occluder", {})
    placement = occluder.get("placement")
    planned = site["occluder"]["planned_footprint_xy_m"]
    center = [sum(point[axis] for point in planned)/len(planned) for axis in (0,1)]
    if (occluder.get("blueprint_filter") != "vehicle.*" or
            not isinstance(placement,dict) or
            (placement.get("x"),placement.get("y")) != tuple(center) or
            placement.get("z") != 0.5 or placement.get("yaw") != 45):
        raise ValueError("Occluder placement differs from map-bound blind-corner candidate")
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
        if occluder.get("blueprint_filter") != "vehicle.*" or not isinstance(placement,dict):
            raise ValueError("Map-bound Native occluder placement and bounded filter required")
        state = config.get("operative_signal_state")
        capture(argparse.Namespace(case_id=config["selected_case_id"],
            operative_state=state,occluder_blueprint=occluder["blueprint_id"],
            occluder_filter=occluder["blueprint_filter"],
            occluder_x=placement["x"],occluder_y=placement["y"],
            occluder_z=placement["z"],occluder_yaw=placement["yaw"],
            output_dir=args.output_dir,host=args.host,port=args.port))
    else:
        parser.error("--check, --output-dir, or --attempt with --output required")


if __name__ == "__main__":
    main()
