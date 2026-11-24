"""Offline exact-case preflight for the 400(2)(a) approach package."""
import argparse
import json
from pathlib import Path

PREFIX = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__"

def check(config):
    case = config.get("selected_case_id", "")
    suffix = case.removeprefix(PREFIX)
    if not case.startswith(PREFIX) or suffix not in (
            "near_centerline", "farther_from_centerline",
            "imaginary_near_centerline", "imaginary_farther_from_centerline"):
        raise ValueError("wrong exact case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-400-2a", "C109705", "motor_vehicle_driver"):
        raise ValueError("wrong frozen law/cell/actor")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("wrong timing contract")
    if config.get("cameras") != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four camera plan missing")
    kind = "imaginary_equidistant" if suffix.startswith("imaginary_") else "marked"
    if config.get("centerline_kind") != kind:
        raise ValueError("centerline construction mismatch")
    target = 2.7 if "farther" in suffix else 1.7
    if config.get("target_approach_offset_m") != target:
        raise ValueError("approach position target mismatch")
    return {"case_id": case, "offline_contract_passed": True,
            "native_map_survey_required": True, "physical_realization": "pending"}


def run_capture(adapter, config, map_packet, output):
    """Execute a reviewed exact case with an injected Native CARLA adapter."""
    selected = check(config)['case_id']
    from native_capture import capture
    return capture(adapter, selected, Path(map_packet), Path(output))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port")
    args=parser.parse_args()
    config=json.loads(Path("config.json").read_text())
    result=check(config)
    if args.check:
        print(json.dumps(result))
    else:
        raise RuntimeError("Native capture and source packet binding unfinished for " + result["case_id"])

if __name__=="__main__":
    main()
