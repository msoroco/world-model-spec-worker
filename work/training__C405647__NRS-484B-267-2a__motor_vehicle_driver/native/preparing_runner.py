"""Exact prospective classification runner for the two preparing alternatives.

This consumes original, source-bound observations. It does not capture pixels,
establish physical motion, or decide a legal reasonable speed.
"""
import argparse
import json
import os
from pathlib import Path

from branch_alternatives import classify

BASE = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver__preparing_to_move__"
BRANCHES = ("visible_vehicle_movement", "visible_driver_hand_signal")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def check_config(config):
    branch = config.get("activation_branch")
    if branch not in BRANCHES or config.get("case_id") != BASE + branch:
        raise ValueError("Exact preparing case identity differs")
    if config.get("law_id") != "NRS-484B-267-2a" or config.get("cell_id") != "C405647":
        raise ValueError("Frozen law or cell identity differs")
    if config.get("actor") != "motor_vehicle_driver" or config.get("duration_frames") != 600 or config.get("rate_hz") != 20:
        raise ValueError("Preparing capture contract differs")
    if tuple(config.get("required_views", ())) != VIEWS or config.get("already_moving") is not False:
        raise ValueError("Preparing source needs four views and no prior movement")
    return {"case_id": config["case_id"], "branch": branch,
            "original_source_required": True, "physical_completion_claimed": False}


def classify_exact(config, evidence):
    check_config(config)
    if evidence.get("case_id") != config["case_id"]:
        raise ValueError("Original observation belongs to another exact case")
    if evidence.get("already_moving") is not False:
        raise ValueError("Preparing case cannot use already-moving source")
    result = classify(evidence)
    if result["observed_activation_branches"] != [config["activation_branch"]]:
        raise ValueError("Source activates another preparing branch")
    result["case_id"] = config["case_id"]
    result["physical_completion_claimed"] = False
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--evidence")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check_config(config), sort_keys=True))
    elif args.evidence:
        print(json.dumps(classify_exact(config, json.loads(Path(args.evidence).read_text())),
                         indent=2, sort_keys=True))
    else:
        if not args.output_dir:
            raise ValueError("Native output path required")
        survey_path = args.site_survey or os.environ.get("SCENARIO_EMERGENCY_SITE_SURVEY")
        if not survey_path:
            raise ValueError("Original same-cell emergency site survey required")
        survey = json.loads(Path(survey_path).read_text())
        if config["activation_branch"] == "visible_vehicle_movement":
            from preparing_movement_capture import execute
        else:
            from preparing_hand_capture import execute
        execute(config, survey, args.output_dir, args.host, args.port)
