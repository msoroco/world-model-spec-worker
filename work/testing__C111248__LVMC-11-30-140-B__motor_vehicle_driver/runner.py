"""Exact blind-person encounter diagnostic bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from blind_encounter import CASE_BY_ID
from native_capture import CAMERAS
from reviewed_sources import prepare


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(source)
    case_id = config["selected_case_id"]
    rows = [item for item in plan["cases"] if item["case_id"] == case_id]
    if len(rows) != 1 or not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact encounter case missing")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    if suffix not in CASE_BY_ID:
        raise ValueError("Unsupported encounter case")
    case = CASE_BY_ID[suffix]
    if config["case"] != {"cue": case.cue, "encounter": case.encounter,
                          "response": case.response, "precaution": case.precaution}:
        raise ValueError("Encounter construction knobs changed")
    if config["case"] != {key: rows[0][key] for key in config["case"]}:
        raise ValueError("Encounter differs from exact plan")
    if config["hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original capture timebase changed")
    if [camera["name"] for camera in config["cameras"]] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Original camera list changed")
    if config["approach_speed_cap_mps"] not in (1.0, 2.0) or (config["approach_speed_cap_mps"] == 1.0 and suffix != "white_contact_stop"):
        raise ValueError("Unapproved approach speed cap")
    if config["required_sources"] != ["reviewed_map_route", "blindness_attestation",
                                      "actually_carried_cue", "original_body_history",
                                      "original_camera_pixels"]:
        raise ValueError("Encounter source contract changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--source-packet")
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic blind-person bundle passed: " + case_id)
        return
    if args.source_packet:
        plan = prepare(Path(args.source_packet))
        if plan["case_id"] != case_id.removeprefix(json.loads((Path(__file__).resolve().parent / "config.json").read_text())["assignment_id"] + "__"):
            raise ValueError("reviewed packet exact case mismatch")
        raise ValueError("reviewed plan bound; Native actor spawn and world ownership require local integration")
    raise ValueError("Reviewed Native map, blindness and actually carried cue sources required")


if __name__ == "__main__":
    main()
