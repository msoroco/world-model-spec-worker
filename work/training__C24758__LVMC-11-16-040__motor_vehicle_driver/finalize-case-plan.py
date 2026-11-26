"""Bind the exact four-camera plan and source observation mapping."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE / "case-plan.json"
plan = json.loads(path.read_text())
plan["camera_plan"] = {
    "profile": "overview1080-capability", "duration_s": 30,
    "composition": "synchronized_four_view_primary",
    "coverage": [
        {"subject": "ego, intersection, and entering roads", "interval": "all 600 frames", "view": "overview"},
        {"subject": "last 100 ft of ego approach", "interval": "all 600 frames", "view": "approach"},
        {"subject": "entering approach and occluder", "interval": "all 600 frames", "view": "reference_corner"},
        {"subject": "driver eye view and intersection sight", "interval": "all 600 frames", "view": "driver_reference"}]}
plan["observations"] = [
    {"name": "ego_pose", "unit": "m,deg", "mandatory": True,
     "purpose": "Original Native position and heading for every frame"},
    {"name": "ego_speed", "unit": "m/s", "mandatory": True,
     "purpose": "Original Native velocity-derived speed"},
    {"name": "distance_to_boundary", "unit": "m", "mandatory": True,
     "purpose": "Source-derived signed distance to intersection entry"},
    {"name": "intersection_sight", "unit": "source-bound review", "mandatory": True,
     "purpose": "Last 100 ft intersection view against original rays and pixels"},
    {"name": "entering_approach_visibility", "unit": "source-bound review", "mandatory": True,
     "purpose": "All entering road visibility to 100 ft"},
    {"name": "intersection_traversal", "unit": "frame interval", "mandatory": True,
     "purpose": "Source-joined interval of ego intersection traversal"}]
for term, mapping in plan["source_observation_mapping"].items():
    mapping["channels"] = ["ego_speed"] if term == "kin.speed" else ["intersection_sight", "entering_approach_visibility"]
    mapping["evidence"] = "Original Native map, ray, pixel and speed sources with independent context review; physical and legal acceptance pending"
path.write_text(json.dumps(plan, indent=2) + "\n")
