"""Independent CPU comparison check for school-bus speed and trip phase."""

import argparse
import json
from pathlib import Path


class ComparisonError(ValueError):
    pass


FIXED_FIELDS = ("map_sha256", "route_sha256", "sidewalk_sha256",
                "school_bus_definition_sha256", "school_bus_exclusions_sha256",
                "bus_blueprint", "driver_actor_id", "camera_plan_sha256",
                "duration_frames")


def audit(records, *, deliberate_differences):
    if len(records) < 2 or not deliberate_differences:
        raise ComparisonError("two records and deliberate difference required")
    for record in records:
        if record.get("format") != "school-bus-delivery-measurement":
            raise ComparisonError("missing sealed school-bus measurement")
        if not record.get("case_id") or not record.get("native_result_sha256"):
            raise ComparisonError("missing case or sealed Native result")
        if record.get("frame_count") != 900 or record.get("full_video_decode") is not True:
            raise ComparisonError("incomplete frame or video evidence")
        if not record.get("actual_pixels") or not record.get("physical_completion"):
            raise ComparisonError("physical visibility or completion unverified")
        for field in FIXED_FIELDS:
            if field not in record or record[field] in (None, ""):
                raise ComparisonError("missing fixed condition: " + field)
    if len({r["case_id"] for r in records}) != len(records) or len({r["native_result_sha256"] for r in records}) != len(records):
        raise ComparisonError("comparison requires separate case captures")
    first = records[0]
    for record in records[1:]:
        for field in FIXED_FIELDS:
            if record[field] != first[field]:
                raise ComparisonError("fixed condition changed: " + field)
    for key in deliberate_differences:
        if any(key not in record.get("observables", {}) for record in records):
            raise ComparisonError("declared difference has no measured observable")
        if len({json.dumps(record["observables"][key], sort_keys=True) for record in records}) < 2:
            raise ComparisonError("declared difference was not realized")
    return {"format": "school-bus-comparison-audit",
            "case_ids": [record["case_id"] for record in records],
            "fixed_conditions_checked": list(FIXED_FIELDS),
            "deliberate_differences": deliberate_differences,
            "status": "measurement_comparable_legal_judgment_unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--records", required=True, type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = json.loads((here / "case-plan.json").read_text())
    selected = [item for item in plan["comparisons"] if item["comparison_id"] == args.comparison]
    if len(selected) != 1:
        raise ComparisonError("unknown exact comparison")
    records = json.loads(args.records.read_text())
    ids = selected[0]["case_ids"]
    if set(records) != set(ids):
        raise ComparisonError("comparison record identities differ")
    result = audit([records[case_id] for case_id in ids],
                   deliberate_differences=selected[0]["deliberate_differences"])
    result["comparison_id"] = args.comparison
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
