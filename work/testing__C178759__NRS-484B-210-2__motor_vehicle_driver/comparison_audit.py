"""Independent CPU comparison check for captured signal cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class ComparisonError(ValueError):
    pass


FIXED_FIELDS = (
    "map_sha256", "paved_boundary_sha256", "right_lane_source_sha256",
    "ego_blueprint", "target_blueprint", "controller_sha256",
    "camera_plan_sha256", "duration_frames", "driver_actor_id",
)


def audit(left: dict, right: dict, *, deliberate_differences: list[str]) -> dict:
    """Compare independently captured measurements; fail closed on missing fields."""
    if not deliberate_differences:
        raise ComparisonError("missing declared deliberate difference")
    for side in (left, right):
        if side.get("format") != "right-pass-delivery-measurement":
            raise ComparisonError("missing sealed signal measurement")
        if not side.get("case_id") or not side.get("native_result_sha256"):
            raise ComparisonError("missing case or sealed Native result")
        if side.get("frame_count") != 900 or side.get("full_video_decode") is not True:
            raise ComparisonError("incomplete frame or video evidence")
        if not side.get("actual_pixels") or not side.get("physical_completion"):
            raise ComparisonError("physical visibility or completion unverified")
        for field in FIXED_FIELDS:
            if field not in side or side[field] in (None, ""):
                raise ComparisonError(f"missing fixed condition: {field}")
    if left["case_id"] == right["case_id"] or left["native_result_sha256"] == right["native_result_sha256"]:
        raise ComparisonError("comparison requires separate case captures")
    for field in FIXED_FIELDS:
        if left[field] != right[field]:
            raise ComparisonError(f"fixed condition changed: {field}")
    if any(key not in left.get("observables", {}) or key not in right.get("observables", {}) for key in deliberate_differences):
        raise ComparisonError("declared difference has no measured observable")
    if all(left["observables"][key] == right["observables"][key] for key in deliberate_differences):
        raise ComparisonError("declared difference was not realized")
    return {"format": "right-pass-comparison-audit", "case_ids": [left["case_id"], right["case_id"]],
            "fixed_conditions_checked": list(FIXED_FIELDS), "deliberate_differences": deliberate_differences,
            "status": "measurement_comparable_legal_judgment_unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--records", required=True, type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = json.loads((here / "case-plan.json").read_text())
    selected = [item for item in plan["comparisons"]
                if item["comparison_id"] == args.comparison]
    if len(selected) != 1:
        raise ComparisonError("unknown exact comparison")
    records = json.loads(args.records.read_text())
    case_ids = selected[0]["case_ids"]
    if set(records) != set(case_ids):
        raise ComparisonError("comparison record identities differ")
    result = audit(records[case_ids[0]], records[case_ids[1]],
                   deliberate_differences=selected[0]["deliberate_differences"])
    result["comparison_id"] = args.comparison
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
