"""Independent original-source check for the selected other-entry-order pair."""
import json
from pathlib import Path

from crossing_precedence import analyze

FIXED_CONTEXT = (
    "native_map_id", "intersection_id", "ego_highway_id", "other_highway_id",
    "ego_road_id", "other_road_id", "crossing_geometry_source",
    "all_entrances_source", "official_device_inventory_source",
    "median_spacing_source", "intersection_polygon_xy_m",
    "same_statutory_crossing", "official_device_controls_crossing",
    "opposite_approach_with_left_turn",
)


def audit_entry_order(left_root: Path, right_root: Path, expected_frames: int) -> dict:
    """Require one sourced other-first and one other-later entry at a fixed crossing."""
    left_root, right_root = Path(left_root), Path(right_root)
    left = analyze(left_root)
    right = analyze(right_root)
    left_context = json.loads((left_root / "junction_context.json").read_text())
    right_context = json.loads((right_root / "junction_context.json").read_text())
    for key in FIXED_CONTEXT:
        if left_context.get(key) != right_context.get(key):
            raise ValueError("Fixed crossing condition changed: " + key)
    if left_context["official_device_controls_crossing"] is not False or left_context["opposite_approach_with_left_turn"] is not False:
        raise ValueError("Entry-order pair requires resolved subsection-1 applicability")
    if left["other_enters_before_ego"] == right["other_enters_before_ego"]:
        raise ValueError("Entry-order comparison lacks observed ordering difference")
    if not (left["other_body_inside_at_ego_entry"] or right["other_body_inside_at_ego_entry"]):
        raise ValueError("Neither source shows other occupancy at ego entry")
    if type(expected_frames) is not int or expected_frames < 3:
        raise ValueError("Expected full frame count required")
    if len(left["samples"]) != expected_frames or len(right["samples"]) != expected_frames:
        raise ValueError("Full comparison duration changed")
    for a, b in zip(left["samples"], right["samples"]):
        if a["frame"] != b["frame"] or a["time_s"] != b["time_s"]:
            raise ValueError("Fixed comparison frame or time changed")
    return {
        "format": "worker-median-crossing-entry-order-comparison",
        "comparison_id": "other_entry_order",
        "expected_frames": expected_frames,
        "left_sources": left["sources"],
        "right_sources": right["sources"],
        "fixed_context_keys": list(FIXED_CONTEXT),
        "left_other_enters_before_ego": left["other_enters_before_ego"],
        "right_other_enters_before_ego": right["other_enters_before_ego"],
        "left_other_inside_at_ego_entry": left["other_body_inside_at_ego_entry"],
        "right_other_inside_at_ego_entry": right["other_body_inside_at_ego_entry"],
        "software_comparison_passed": True,
        "physical_acceptance_claimed": False,
        "legal_conclusion": "unresolved",
    }
