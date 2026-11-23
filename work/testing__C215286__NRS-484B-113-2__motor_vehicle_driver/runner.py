"""Exact crosswalk case preflight; Native capture remains a separate deliverable."""

import argparse
import json
from pathlib import Path


TARGETS = {"reverse_clear": "disjoint", "reverse_tangent": "contact",
           "reverse_overlap": "overlap"}


def check(scene):
    if scene.get("law_id") != "NRS-484B-113-2" or scene.get("cell_id") != "C215286":
        raise ValueError("wrong frozen law or cell")
    if scene.get("actor") != "motor_vehicle_driver":
        raise ValueError("wrong frozen actor")
    case = scene.get("case_id", "").split("__")[-1]
    if TARGETS.get(case) != scene.get("target_physical_relation"):
        raise ValueError("wrong exact case target")
    if scene.get("fps") != 20 or scene.get("camera_names") != [
            "approach", "crossing", "overhead", "reference_corner"]:
        raise ValueError("missing common capture plan")
    return {"case_id": scene["case_id"], "target": TARGETS[case],
            "native_source_packet_required": True, "physical_realization": "pending"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port")
    args = parser.parse_args()
    scene = json.loads(Path("scene.json").read_text())
    result = check(scene)
    if args.check:
        print(json.dumps(result))
    else:
        raise RuntimeError("Native source packet/capture binding unfinished for " + result["case_id"])


if __name__ == "__main__":
    main()
