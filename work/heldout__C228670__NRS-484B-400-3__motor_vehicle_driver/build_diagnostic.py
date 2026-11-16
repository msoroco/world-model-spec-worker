"""Create the source-shaped CPU diagnostic for the first exact turn case."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + "__centerline_approach_left_curb_departure"
BASE = REPO / "work/heldout__C126064__LVMC-11-12-020__motor_vehicle_driver/button-indicated-diagnostic.json"


def build():
    fixture = json.loads(BASE.read_text())
    files = fixture["files"]
    source = {
        "provenance_kind": "native_xodr_survey",
        "map_name": "CPU diagnostic left-turn map; physical site unverified",
        "intersection_kind": "public_highway_non_alley",
        "approach_directions": 2,
        "destination_directions": 1,
        "waypoints": [
            {"road_id": 1, "lane_id": -1, "s": 1, "xy_m": [-8, 0]},
            {"road_id": 1, "lane_id": -1, "s": 8, "xy_m": [0, 0]},
            {"road_id": 2, "lane_id": -1, "s": 2, "xy_m": [8, 6]},
        ],
        "approach_centerline_xy_m": [[-10, 1.2], [0, 1.2]],
        "destination_left_curb_xy_m": [[6.8, 0], [6.8, 10]],
        "intersection_entry_xy_m": [0, 1.2],
        "approach_right_half_width_m": 3.5,
        "destination_one_way_width_m": 3.5,
        "public_access_verified": False,
        "physical_site_verified": False,
    }
    raw = json.dumps(source, sort_keys=True) + "\n"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    files["route_survey_original.json"] = raw
    files["route_survey_capture_receipt.json"] = json.dumps({
        "case_id": CASE, "source_path": "route_survey_original.json",
        "source_sha256": digest, "map_name": source["map_name"],
        "native_route_verified": True, "diagnostic_fixture": True,
        "physical_turn_completed": False, "public_access_verified": False,
    }) + "\n"
    body = [json.loads(line) for line in files["turn_body.jsonl"].splitlines() if line]
    for index, row in enumerate(body):
        row["phase"] = "approach" if index < 3 else "entry" if index < 6 else "departure"
        row["body_corners_xy_m"] = row.pop("corners_xy_m")
    files["body_corners_original.jsonl"] = "".join(json.dumps(row) + "\n" for row in body)
    for irrelevant in ("turn_body.jsonl", "authority_source_original.json",
                       "marked_intersection.json", "turn_originals.jsonl",
                       "ego_turn_motion.jsonl", "ego_signal_audio.jsonl"):
        files.pop(irrelevant, None)
    files["fixture-provenance.json"] = json.dumps({
        "scope": "CPU diagnostic only", "diagnostic_fixture": True,
        "actual_native_capture": False, "public_highway_access_verified": False,
        "physical_camera_pixels_verified": False,
    }) + "\n"
    diagnostic = ROOT / "diagnostic.json"
    diagnostic.write_text(json.dumps(fixture, separators=(",", ":")) + "\n")
    diagnostic_sha = hashlib.sha256(diagnostic.read_bytes()).hexdigest()
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json",
                           "source": "work/" + ROOT.name + "/diagnostic.json",
                           "sha256": diagnostic_sha}],
              "generator": {"source": "work/" + ROOT.name + "/diagnostic.json",
                            "sha256": diagnostic_sha}}
    (ROOT / "recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    return {"diagnostic_sha256": diagnostic_sha, "bytes": diagnostic.stat().st_size,
            "source_sha256": digest}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
