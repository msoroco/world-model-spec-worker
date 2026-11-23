"""Independent CPU comparison check for captured signal cases."""
from __future__ import annotations


class ComparisonError(ValueError):
    pass


FIXED_FIELDS = (
    "map_sha256", "intersection_polygon_sha256", "route_connectivity_sha256",
    "ego_blueprint", "controller_sha256", "camera_plan_sha256", "duration_frames",
    "selected_route_id", "selected_signal_id", "device_route_binding_sha256",
)


def audit(left: dict, right: dict, *, deliberate_differences: list[str]) -> dict:
    """Compare independently captured measurements; fail closed on missing fields."""
    if not deliberate_differences:
        raise ComparisonError("missing declared deliberate difference")
    for side in (left, right):
        if side.get("format") != "signal-delivery-measurement":
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
    return {"format": "signal-comparison-audit", "case_ids": [left["case_id"], right["case_id"]],
            "fixed_conditions_checked": list(FIXED_FIELDS), "deliberate_differences": deliberate_differences,
            "status": "measurement_comparable_legal_judgment_unresolved"}
