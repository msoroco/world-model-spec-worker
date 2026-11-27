"""Independent exact-case comparison of source-joined turn-position records."""

import argparse
import json
from pathlib import Path


class ComparisonError(ValueError):
    pass


BASE_FIXED = ("map_sha256", "public_highway_source_sha256",
              "intersection_source_sha256", "connected_right_exit_sha256",
              "ego_blueprint", "driver_actor_id", "right_turn_intention_sha256",
              "camera_plan_sha256", "duration_frames")
DESIGN_FIXED = ("lane_design_source_sha256", "qualification_source_sha256")


def audit(records, *, deliberate_differences, comparison_id):
    if len(records) < 2 or not deliberate_differences:
        raise ComparisonError("separate exact records and deliberate differences required")
    fields = BASE_FIXED if comparison_id == "conditional_lane_design" else BASE_FIXED + DESIGN_FIXED
    for record in records:
        if record.get("format") != "turn-position-delivery-measurement" or not record.get("case_id") or not record.get("native_result_sha256"):
            raise ComparisonError("missing sealed original Native measurement")
        if record.get("frame_count") != 900 or record.get("full_video_decode") is not True or not record.get("actual_pixels") or not record.get("physical_completion"):
            raise ComparisonError("incomplete physical, source or pixel evidence")
        if not record.get("approach_source_sha256") or not record.get("turn_source_sha256"):
            raise ComparisonError("original approach/turn interval sources missing")
        for field in fields:
            if record.get(field) in (None, ""):
                raise ComparisonError("missing fixed condition: " + field)
    if len({r["case_id"] for r in records}) != len(records) or len({r["native_result_sha256"] for r in records}) != len(records):
        raise ComparisonError("comparison requires separate original captures")
    first = records[0]
    for record in records[1:]:
        for field in fields:
            if record[field] != first[field]:
                raise ComparisonError("fixed condition changed: " + field)
    for field in deliberate_differences:
        values = [record.get("observables", {}).get(field) for record in records]
        if None in values or len({json.dumps(value, sort_keys=True) for value in values}) < 2:
            raise ComparisonError("deliberate difference absent: " + field)
    return {"format": "turn-position-comparison-audit", "comparison_id": comparison_id,
            "case_ids": [r["case_id"] for r in records],
            "fixed_conditions_checked": list(fields),
            "deliberate_differences": deliberate_differences,
            "status": "measurement_comparable_legal_judgment_unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--records", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = json.loads((here / "case-plan.json").read_text())
    selected = [row for row in plan["comparisons"] if row["comparison_id"] == args.comparison]
    if len(selected) != 1:
        raise ComparisonError("unknown exact comparison")
    records = json.loads(args.records.read_text())
    if set(records) != set(selected[0]["case_ids"]):
        raise ComparisonError("comparison identities changed")
    result = audit([records[case] for case in selected[0]["case_ids"]],
                   deliberate_differences=selected[0]["deliberate_differences"],
                   comparison_id=args.comparison)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
