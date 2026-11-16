"""Compare three retained turn-indication forms under one sourced route."""

import argparse
import hashlib
import json
from pathlib import Path

from turn_marking import analyze_original_sources


FORMS = ("marker", "button", "other_indication")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError("Form comparison needs three exact follow cases")
    rows = []
    for form, attempt in zip(FORMS, map(Path, attempts)):
        measured = analyze_original_sources(attempt)
        source = json.loads((attempt / "turn_indication_original.json").read_text())
        route = json.loads((attempt / "turn_route_plan.json").read_text())
        config = json.loads((attempt / "config.json").read_text())
        case_id = measured["case_id"]
        if not case_id.endswith("__" + form + "_follow") or source["indication_form"] != form:
            raise ValueError("Selected case and original indication form differ")
        if route["route_variant"] != "follow" or route["course_xy_m"] != route["target_route_xy_m"]:
            raise ValueError("Form comparison changed the follow route")
        if not source.get("authority_document") or not source.get("map_name"):
            raise ValueError("Indication source context missing")
        rows.append({
            "form": form,
            "case_id": case_id,
            "fixed": {
                "intersection_id": source["intersection_id"],
                "map_name": source["map_name"],
                "authority_claim": source["authority_document"],
                "course": source["indicated_course_xy_m"],
                "route": route["target_route_xy_m"],
                "duration_s": config["duration_s"],
                "cameras": config["cameras"],
                "motion_sha256": sha(attempt / "turn_body_original.jsonl"),
                "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            },
            "sources": {
                "indication_sha256": sha(attempt / "turn_indication_original.json"),
                "route_sha256": sha(attempt / "turn_route_plan.json"),
                "camera_sha256": {name: sha(attempt / (name + ".mkv")) for name in CAMERAS},
            },
            "samples": len(measured["samples"]),
        })
    if any(row["fixed"] != rows[0]["fixed"] for row in rows[1:]):
        raise ValueError("Fixed intersection, route, motion, duration or cameras changed")
    if any(row["samples"] != rows[0]["samples"] for row in rows[1:]):
        raise ValueError("Original sample coverage changed")
    if len({row["sources"]["indication_sha256"] for row in rows}) != 3:
        raise ValueError("Distinct sourced indication forms absent")
    return {
        "format": "worker-indication-form-comparison",
        "comparison_id": "indication_form",
        "case_ids": [row["case_id"] for row in rows],
        "fixed_conditions_verified": True,
        "rows": rows,
        "municipal_authorization_verified": False,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--button", type=Path, required=True)
    parser.add_argument("--other", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit((args.marker, args.button, args.other))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("indication_form_audit_passed", len(result["rows"]))
