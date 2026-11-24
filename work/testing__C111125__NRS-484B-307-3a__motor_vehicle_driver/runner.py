"""Exact dual-green diagnostic preflight; original sources required for capture."""
import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver"
SUFFIXES = ("dual_clear", "dual_vehicle_present", "dual_pedestrian_present", "dual_pedestrian_late")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    raw = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["plan_sha256"]:
        raise ValueError("dual-green case plan changed")
    case_id = config["selected_case_id"]
    if case_id not in {ASSIGNMENT + "__" + s for s in SUFFIXES}:
        raise ValueError("foreign dual-green case")
    plan = json.loads(raw)
    rows = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(rows) != 1 or rows[0]["scenario_parameters"] != config["scenario_parameters"]:
        raise ValueError("dual-green case parameters changed")
    if config["fps"] != 20 or config["frame_count"] != 900 or tuple(config["cameras"]) != CAMERAS:
        raise ValueError("dual-green capture contract changed")
    if config["required_sources"] != ["surveyed_native_site", "official_dual_aspect_lamp_packets", "original_camera_png", "lawful_use_packets"]:
        raise ValueError("dual-green original source contract changed")
    for name, digest in config["code_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("dual-green code source changed: " + name)
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic dual-green case passed: " + case_id)
        return
    if not __import__("os").environ.get("SCENARIO_DUAL_GREEN_SOURCE_ROOT"):
        raise ValueError("Reviewed original dual-aspect site, lamp, lawful-use and camera sources required")
    from native_runner import run
    run(args.host, args.port, args.output_dir, case_id)


if __name__ == "__main__":
    main()
