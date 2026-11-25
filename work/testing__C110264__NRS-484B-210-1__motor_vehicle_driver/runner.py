"""Exact paragraph-(a) right-pass bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from pass_right_capture import CAMERAS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    case = config["selected_case_id"]
    entries = [row for row in json.loads(source)["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    variant = case.removeprefix(config["assignment_id"] + "__")
    if variant not in ("left_signal", "left_turn", "neither"):
        raise ValueError("Unknown exact paragraph-(a) variant")
    if entries[0]["draft_variables"]["controller"]["target"] != variant or config["target_behavior_request"] != variant:
        raise ValueError("Target request changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    if config["native_cameras"] != list(CAMERAS):
        raise ValueError("Original four-camera profile changed")
    if [(item["name"], item["width"], item["height"]) for item in config["cameras"]] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("Canonical four-view profile changed")
    if config["required_sources"] != ["reviewed_map", "ego_target_trace", "frame_map", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    if config["native_setup_role"] not in ("primary", "fallback1"):
        raise ValueError("Unknown reviewed Native setup role")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic right-pass bundle passed: " + case)
        return
    raise ValueError("Reviewed Native paved corridor, actor motion and original camera capture required")


if __name__ == "__main__":
    main()
