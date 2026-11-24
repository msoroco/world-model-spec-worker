"""Source-bound diagnostic measurements for the selected dual-green cases.

This produces factual measurements only. Native result, Core conversion and
physical acceptance require the separate selected delivery pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from dual_green import measure_original, require
from saved_attempt import check_case_observation
from source_handoff import load_handoff
from native_publication import publish


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def hash_sources(root, names):
    return {name: hashlib.sha256(source(root, name).read_bytes()).hexdigest()
            for name in names}


def measure_dual_aspect(site, measured, handoff):
    return {"official_head_id": site["official_head_id"],
            "facing_approach_id": site["ego_approach_id"],
            "arrow_direction": site["arrow_direction"],
            "first_exhibition_frame": measured["exhibition"]["frame"],
            "source_frame_count": handoff["frame_count"],
            "legal_signal_verdict": None}


def measure_straight_context(site, measured, handoff):
    return {"movement": site["ego_movement"],
            "permission_source": site["movement_permission_source_path"],
            "permission_review": site["straight_permission_review"],
            "intersection_entry_observed": any(row["ego_in_intersection"]
                                               for row in measured["records"]),
            "legal_permission_verdict": None}


def measure_pedestrian_context(site, measured, handoff):
    pedestrians = [user for row in measured["records"]
                   for user in row["other_users"] if user["kind"] == "pedestrian"]
    at_exhibition = [user for user in measured["exhibition"]["other_users"]
                     if user["kind"] == "pedestrian"]
    return {"observed_pedestrian_ids": sorted({user["id"] for user in pedestrians}),
            "adjacent_crosswalk_at_exhibition": sorted(user["id"] for user in at_exhibition
                                                       if user["region"] == "adjacent_crosswalk"),
            "lawful_use_source_paths": sorted({user["lawful_use_source"] for user in pedestrians}),
            "legal_yield_verdict": None}


def measure_vehicle_context(site, measured, handoff):
    vehicles = [user for row in measured["records"]
                for user in row["other_users"] if user["kind"] == "motor_vehicle"]
    at_exhibition = [user for user in measured["exhibition"]["other_users"]
                     if user["kind"] == "motor_vehicle"]
    return {"observed_vehicle_ids": sorted({user["id"] for user in vehicles}),
            "intersection_at_exhibition": sorted(user["id"] for user in at_exhibition
                                                  if user["region"] == "intersection"),
            "lawful_use_source_paths": sorted({user["lawful_use_source"] for user in vehicles}),
            "legal_yield_verdict": None}


METHODS = (
    ("dual_aspect_observation", measure_dual_aspect,
     ("site.json", "original-events.json", "original-source-handoff.json")),
    ("straight_movement_context", measure_straight_context,
     ("site.json", "original-events.json")),
    ("pedestrian_yield_observation", measure_pedestrian_context,
     ("original-events.json", "original-source-handoff.json")),
    ("vehicle_yield_observation", measure_vehicle_context,
     ("original-events.json", "original-source-handoff.json")),
)


def build(attempt):
    root = Path(attempt)
    config = json.loads(source(root, "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    require(case_id.startswith("testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"),
            "wrong selected dual-green case")
    site = json.loads(source(root, "site.json").read_text(encoding="utf-8"))
    event = source(root, "original-events.json")
    event_ref = {"path": event.name,
                 "sha256": hashlib.sha256(event.read_bytes()).hexdigest()}
    measured = measure_original(site, root, event_ref)
    check_case_observation(case_id, measured)
    handoff = load_handoff(source(root, "original-source-handoff.json"),
                           root, site, case_id,
                           expected_frames=len(measured["records"]),
                           diagnostic_fixture=config.get("diagnostic_only") is True)
    require([row["frame"] for row in measured["records"]] ==
            list(range(handoff["first_frame"], handoff["last_frame"] + 1)),
            "original source handoff/event frame join differs")
    original_rows = json.loads(event.read_text(encoding="utf-8"))
    for row in original_rows:
        reference = handoff["lamp_ref_for_frame"](row["frame"])
        require(reference["path"] == row["aspect_observation_source"] and
                reference["sha256"] == row["aspect_observation_sha256"],
                "original lamp handoff/event reference differs")
        for user in row["other_users"]:
            lawful = handoff["lawful_use_ref_for_frame"](row["frame"], user["id"])
            require(lawful["path"] == user["lawful_use_source"] and
                    lawful["sha256"] == user["lawful_use_sha256"],
                    "original lawful-use handoff/event reference differs")
    values = {name: {"value": method(site, measured, handoff),
                     "method": method.__name__,
                     "sources": hash_sources(root, names)}
              for name, method, names in METHODS}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": values, "analysis_complete": True,
            "legal_verdict_claimed": False,
            "limitations": ["Permission, lawful use and right of way require source-backed review.",
                            "Diagnostic packets and pixels do not establish physical acceptance."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build(args.attempt)
    output = Path(args.output)
    require(not output.exists(), "analysis output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if (Path(args.attempt) / "capture" / "manifest.json").is_file():
        publish(args.attempt, report)


if __name__ == "__main__":
    main()
