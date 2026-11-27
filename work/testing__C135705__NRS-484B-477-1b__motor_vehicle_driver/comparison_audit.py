"""Independent original-source contrasts for the exact other-alley branch."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from width_measurement import ASSIGNMENT, measure_saved

MEMBERS = {
    "below_at_10ft": ("width_9_9ft", "width_10_0ft"),
    "at_above_10ft": ("width_10_0ft", "width_10_1ft"),
    "other_vehicle_condition": ("other_vehicle_close", "other_vehicle_far"),
    "ordinance_exception": ("width_9_9ft", "ordinance_otherwise"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed(geometry, comparison):
    value = copy.deepcopy(geometry)
    value.pop("case_id", None)
    if comparison == "ordinance_exception":
        value.pop("ordinance_status", None)
        value.pop("ordinance_source", None)
    return value


def audit(attempts, comparison, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != ASSIGNMENT + "__" + comparison:
        raise ValueError("exact other-alley comparison identity differs")
    if comparison not in MEMBERS or len(attempts) != 2:
        raise ValueError("other-alley comparison members differ")
    case_ids = [ASSIGNMENT + "__" + name for name in MEMBERS[comparison]]
    if row["case_ids"] != case_ids:
        raise ValueError("other-alley comparison plan/member order differs")
    measurements = []
    geometry = []
    histories = []
    diagnostic = []
    for attempt, case_id in zip(attempts, case_ids):
        source = Path(attempt) / "original-attempt"
        inventory = json.loads((source / "inventory.json").read_text())
        is_diagnostic = inventory.get("diagnostic_fixture") is True
        diagnostic.append(is_diagnostic)
        measurements.append(measure_saved(source, case_id,
                                          expected_frames=9 if is_diagnostic else 900))
        geometry.append(json.loads((source / "alley_geometry.json").read_text()))
        histories.append(json.loads((source / "width_history.json").read_text())["samples"])
    if fixed(geometry[0], comparison) != fixed(geometry[1], comparison):
        raise ValueError("fixed original alley, survey or vehicle context differs")
    configs = [json.loads((Path(attempt) / "config.json").read_text()) for attempt in attempts]
    if any((cfg["duration_s"], cfg["rate_hz"], cfg["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for cfg in configs[1:]):
        raise ValueError("fixed camera and duration context differs")
    widths = [m["minimum_available_continuous_width_ft"] for m in measurements]
    if comparison == "below_at_10ft":
        if abs(widths[0] - 9.9) > .05 or abs(widths[1] - 10) > .05 or widths[0] >= widths[1]:
            raise ValueError("original below/at 10-foot width contrast differs")
    elif comparison == "at_above_10ft":
        if abs(widths[0] - 10) > .05 or abs(widths[1] - 10.1) > .05 or widths[0] >= widths[1]:
            raise ValueError("original at/above 10-foot width contrast differs")
    elif comparison == "other_vehicle_condition":
        close = [r for r in histories[0] if r["phase"] == "parked_hold"]
        far = [r for r in histories[1] if r["phase"] == "parked_hold"]
        if not (all(r["other_body_polygons_m"] for r in close + far) and
                all(r["other_vehicle_id"] for r in close + far) and widths[0] < widths[1]):
            raise ValueError("original other-vehicle position/width contrast differs")
        if [r["ego_body_polygon_m"] for r in close] != [r["ego_body_polygon_m"] for r in far]:
            raise ValueError("fixed parked ego footprint differs")
    else:
        if not (geometry[0]["ordinance_status"] == "unresolved" and
                geometry[1]["ordinance_status"] == "otherwise_provides" and
                abs(widths[0] - widths[1]) <= 1e-6):
            raise ValueError("original ordinance status/width contrast differs")
        if [r["ego_body_polygon_m"] for r in histories[0]] != [r["ego_body_polygon_m"] for r in histories[1]]:
            raise ValueError("fixed original parked geometry differs")
    return {"format": "c135705-independent-other-alley-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": case_ids, "source_geometry_sha256": [sha(Path(a) / "original-attempt/alley_geometry.json") for a in attempts],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "measured_available_continuous_width_ft": widths,
            "diagnostic_fixture": all(diagnostic), "physical_acceptance": False,
            "free_movement_judgment": "unresolved", "ordinance_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    result = audit(args.attempt, args.comparison, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
