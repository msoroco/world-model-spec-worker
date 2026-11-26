"""Independent source-joined comparison protocol for right-turn-lane purpose."""
import argparse
import json
from pathlib import Path

class ComparisonError(ValueError):
    pass

FIXED_FIELDS = ("map_sha256", "public_highway_source_sha256", "exclusive_lane_source_sha256", "connected_right_exit_sha256", "ego_blueprint", "driver_actor_id", "camera_plan_sha256", "duration_frames")

def audit(records, *, deliberate_differences):
    if len(records) < 2 or not deliberate_differences:
        raise ComparisonError("separate records and deliberate differences required")
    for record in records:
        if record.get("format") != "right-turn-lane-delivery-measurement" or not record.get("case_id") or not record.get("native_result_sha256"):
            raise ComparisonError("missing sealed Native measurement")
        if record.get("frame_count") != 900 or record.get("full_video_decode") is not True or not record.get("actual_pixels") or not record.get("physical_completion"):
            raise ComparisonError("incomplete physical or pixel evidence")
        for field in FIXED_FIELDS:
            if record.get(field) in (None, ""):
                raise ComparisonError("missing fixed condition: " + field)
    if len({r["case_id"] for r in records}) != len(records) or len({r["native_result_sha256"] for r in records}) != len(records):
        raise ComparisonError("comparison requires separate captures")
    first = records[0]
    for record in records[1:]:
        for field in FIXED_FIELDS:
            if record[field] != first[field]:
                raise ComparisonError("fixed condition changed: " + field)
    for field in deliberate_differences:
        values = [record.get("observables", {}).get(field) for record in records]
        if None in values or len({json.dumps(v, sort_keys=True) for v in values}) < 2:
            raise ComparisonError("deliberate difference absent: " + field)
    return {"format": "right-turn-lane-comparison-audit", "case_ids": [r["case_id"] for r in records], "fixed_conditions_checked": list(FIXED_FIELDS), "deliberate_differences": deliberate_differences, "status": "measurement_comparable_legal_judgment_unresolved"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--records", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = json.loads((here / "case-plan.json").read_text())
    selected = [x for x in plan["comparisons"] if x["comparison_id"] == args.comparison]
    if len(selected) != 1:
        raise ComparisonError("unknown comparison")
    records = json.loads(args.records.read_text())
    if set(records) != set(selected[0]["case_ids"]):
        raise ComparisonError("comparison identities changed")
    result = audit([records[x] for x in selected[0]["case_ids"]], deliberate_differences=selected[0]["deliberate_differences"])
    result["comparison_id"] = args.comparison
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
