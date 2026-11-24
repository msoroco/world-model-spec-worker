"""Validate the authored emergency approach source contract before Native capture."""
import argparse
import json
from pathlib import Path
from geometry import check as check_geometry, INTERSECTION_X_M
from motion import check as check_motion

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    if config["frames"] != 600 or config["rate_hz"] != 20:
        raise ValueError("Exact 30-second recording required")
    if config["cell_id"] != "C109028" or config["law_id"] != "NRS-484D-400-5" or \
            config["actor"] != "emergency_vehicle_driver":
        raise ValueError("Frozen assignment identity differs")
    if set(config["camera_sources"]) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("Four source cameras required")
    if config["vehicle_actor_id"] == config["other_vehicle_actor_id"]:
        raise ValueError("Distinct vehicle identities required")
    if config["intersection_x_m"] != INTERSECTION_X_M:
        raise ValueError("Approach geometry differs")
    geometry = check_geometry()
    motion = check_motion(config)
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "four_source_cameras_planned": True,
            "authored_geometry": geometry, "control_policy": motion,
            "native_executed": False,
            "siren_output_observed": False, "acoustic_range_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads((HERE / "config.json").read_text())
    plan = check()
    if args.check:
        print(json.dumps(plan, sort_keys=True))
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("Explicit materialized output and owned Native endpoint required")
    from capture_native import execute
    print(json.dumps(execute(config, args.output_dir, args.host, args.port), sort_keys=True))


if __name__ == "__main__":
    main()
