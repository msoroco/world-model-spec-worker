"""Independent observed-source comparison for exact crossing cases."""

from site_geometry import assess_site


def compare_marking_cases(unmarked: dict, marked: dict) -> dict:
    left, right = assess_site(unmarked), assess_site(marked)
    if left["marked_crosswalk_present"] or not right["marked_crosswalk_present"]:
        raise ValueError("marking difference not observed")
    fixed = ("between_junction_ids", "device_ids", "device_operation_observed", "crosses_both_highway_banks")
    if any(left[k] != right[k] for k in fixed):
        raise ValueError("comparison site or operating controls changed")
    for source in ("map", "devices", "highway"):
        if left["source_sha256"][source] != right["source_sha256"][source]:
            raise ValueError(f"fixed source changed: {source}")
    if abs(left["crossing_station_fraction"] - right["crossing_station_fraction"]) > 1e-9:
        raise ValueError("crossing station changed")
    return {"comparison_id": "between_intersections_marking", "case_status": "source_measurements_compared", "unmarked": left, "marked": right}


def compare_operation_cases(operating: dict, inactive: dict) -> dict:
    left = assess_site(operating)
    right = assess_site(inactive, require_operating=False)
    if right["device_operation_observed"]:
        raise ValueError("inactive device difference not observed")
    for key in ("between_junction_ids", "crossing_station_fraction", "crosses_both_highway_banks", "device_ids", "marked_crosswalk_present"):
        if left[key] != right[key]:
            raise ValueError(f"fixed condition changed: {key}")
    for source in ("map", "route", "markings", "highway"):
        if left["source_sha256"][source] != right["source_sha256"][source]:
            raise ValueError(f"fixed source changed: {source}")
    return {"comparison_id": "both_devices_operating", "case_status": "source_measurements_compared", "operating": left, "inactive": right}
