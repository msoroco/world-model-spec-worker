"""Independent saved-source comparison for the NRS 486.341 planned pair.

This audit compares measured spatial evidence, never decides deprivation or
legal compliance. It recomputes each case from its original source packet.
"""

import argparse
import json
import tempfile
from pathlib import Path

from finalize_lane_use import finalize_bound


FIXED = ("law_id", "cell_id", "actor", "map_name", "protected_blueprint",
         "subject_blueprint", "rate_hz", "duration_s", "cameras",
         "protected_controller", "subject_controller")
SETTINGS = ("full_lane_available", "blocked_by_ego")


def _case(root):
    root = Path(root)
    config_path = root / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads(config_path.read_text())
    if config.get("requested_setting") not in SETTINGS:
        raise ValueError("Unknown exact comparison setting")
    if any(key not in config for key in FIXED):
        raise ValueError("Fixed comparison configuration is incomplete")
    with tempfile.TemporaryDirectory() as directory:
        measured = Path(directory) / "measured.jsonl"
        receipt = finalize_bound(root, measured)
        rows = [json.loads(line) for line in measured.read_text().splitlines()]
    if len(rows) < 2:
        raise ValueError("Insufficient original measurement history")
    return config, receipt, rows


def compare(first, second):
    left, left_receipt, left_rows = _case(first)
    right, right_receipt, right_rows = _case(second)
    if left["case_id"] == right["case_id"]:
        raise ValueError("Comparison requires distinct exact cases")
    if {left["requested_setting"], right["requested_setting"]} != set(SETTINGS):
        raise ValueError("Comparison settings do not span both planned cases")
    for key in FIXED:
        if left[key] != right[key]:
            raise ValueError("Fixed comparison condition differs: " + key)
    if len(left_rows) != len(right_rows):
        raise ValueError("Comparison capture durations differ")
    left_overlap = [row["ego_lane_overlap_fraction"] for row in left_rows]
    right_overlap = [row["ego_lane_overlap_fraction"] for row in right_rows]
    left_gap = [row["footprint_surface_gap_m"] for row in left_rows]
    right_gap = [row["footprint_surface_gap_m"] for row in right_rows]
    if left_overlap == right_overlap and left_gap == right_gap:
        raise ValueError("Declared comparison has no measured spatial difference")
    return {
        "format": "worker-lane-use-comparison-audit",
        "case_ids": [left["case_id"], right["case_id"]],
        "fixed_conditions_checked": list(FIXED),
        "deliberate_difference": "subject lateral lane occupancy and surface gap",
        "requested_settings": [left["requested_setting"], right["requested_setting"]],
        "measured_ego_lane_overlap_ranges": [[min(left_overlap), max(left_overlap)],
                                             [min(right_overlap), max(right_overlap)]],
        "measured_surface_gap_ranges_m": [[min(left_gap), max(left_gap)],
                                          [min(right_gap), max(right_gap)]],
        "source_receipts": [left_receipt, right_receipt],
        "passed": True,
        "physical_completion_claimed": False,
        "legal_verdict_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.first, args.second), sort_keys=True))
