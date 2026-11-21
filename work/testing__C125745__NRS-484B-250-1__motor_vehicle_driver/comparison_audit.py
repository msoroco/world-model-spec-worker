"""Independent source-only entry-order comparison for the stop-sign cell."""

import hashlib
import json
from pathlib import Path

from crossing_measurements import analyze


FIXED = ("native_map_id", "intersection_id", "ego_highway_id",
         "other_highway_id", "ego_road_id", "other_road_id",
         "native_stop_sign_id", "sign_governance_source",
         "stop_sign_video_source", "intersection_polygon_source",
         "intersection_polygon_xy_m", "stop_sign_erected",
         "stop_sign_governed_road_id")


def _source(root, name):
    path = Path(root) / name
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def compare(other_first_root, ego_first_root, expected_frames=1100):
    """Require a controlled changed order; return measurements, never a verdict."""
    if type(expected_frames) is not int or expected_frames < 3:
        raise ValueError("Expected full frame count required")
    first = analyze(Path(other_first_root))
    second = analyze(Path(ego_first_root))
    left, left_sha = _source(other_first_root, "junction_context.json")
    right, right_sha = _source(ego_first_root, "junction_context.json")
    if any(left.get(key) != right.get(key) for key in FIXED):
        raise ValueError("Fixed stop-sign crossing context changed")
    if len(first["samples"]) != expected_frames or len(second["samples"]) != expected_frames:
        raise ValueError("Incomplete original frame history")
    left_times = [(row["frame"], row["time_s"]) for row in first["samples"]]
    right_times = [(row["frame"], row["time_s"]) for row in second["samples"]]
    if left_times != right_times:
        raise ValueError("Comparison original frame/time sequence changed")
    if first["other_entered_before_ego_observed"] is not True:
        raise ValueError("Other-first source did not measure requested order")
    if second["other_entered_before_ego_observed"] is not False:
        raise ValueError("Ego-first source did not measure requested order")
    if first["first_body_entry"]["ego"]["time_s"] == first["first_body_entry"]["other"]["time_s"] or \
            second["first_body_entry"]["ego"]["time_s"] == second["first_body_entry"]["other"]["time_s"]:
        raise ValueError("Tied entry does not establish order")
    return {"format": "worker-stop-sign-entry-comparison",
            "expected_frames": expected_frames,
            "fixed_context_sha256": [left_sha, right_sha],
            "source_sha256": [first["sources"], second["sources"]],
            "other_first_entries": first["first_body_entry"],
            "ego_first_entries": second["first_body_entry"],
            "official_device_exclusion_judgment": "unresolved",
            "physical_acceptance_claimed": False}
