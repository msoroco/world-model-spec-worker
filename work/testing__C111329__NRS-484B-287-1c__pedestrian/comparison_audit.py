"""Independent observed-source comparison for exact crossing cases."""

from site_geometry import assess_site


def compare_marking_cases(unmarked: dict, marked: dict) -> dict:
    left, right = assess_site(unmarked), assess_site(marked)
    if left["marked_crosswalk_present"] or not right["marked_crosswalk_present"]:
        raise ValueError("marking difference not observed")
    fixed = ("between_junction_ids", "device_ids", "device_operation_observed", "crosses_both_highway_banks")
    if any(left[k] != right[k] for k in fixed):
        raise ValueError("comparison site or operating controls changed")
    for source in ("map", "route", "devices", "highway"):
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


def compare_delivery_audits(comparison_id: str, first: dict, second: dict) -> dict:
    """Require two distinct sealed attempts and only the declared source change."""
    from delivery_audit import CASES

    cases = {
        "between_intersections_marking": (
            "midblock_unmarked_operating", "midblock_marked_operating", "markings"),
        "both_devices_operating": (
            "midblock_unmarked_operating", "midblock_unmarked_inactive", "devices"),
    }
    if comparison_id not in cases:
        raise ValueError("unknown exact comparison")
    left_suffix, right_suffix, changing_source = cases[comparison_id]
    rows = (first, second)
    if any(row.get("format") != "worker-pedestrian-delivery-audit" or
           row.get("case_id") not in CASES or row.get("diagnostic_fixture") is not False or
           not isinstance(row.get("native_provenance"), dict) for row in rows):
        raise ValueError("two sealed original delivery audits required")
    if not first["case_id"].endswith(left_suffix) or not second["case_id"].endswith(right_suffix):
        raise ValueError("comparison exact case ordering differs")
    if first["source_observation_sha256"] == second["source_observation_sha256"] or \
       first["native_provenance"]["seal_sha256"] == second["native_provenance"]["seal_sha256"]:
        raise ValueError("comparison requires two distinct original Native attempts")
    if first["frame_count"] != second["frame_count"] or \
       first["camera_names"] != second["camera_names"] or \
       first["full_pixel_decodes"] != second["full_pixel_decodes"]:
        raise ValueError("comparison duration or camera policy changed")
    for source in ("map", "route", "devices", "markings", "highway"):
        if source != changing_source and first["source_sha256"][source] != second["source_sha256"][source]:
            raise ValueError("fixed comparison source changed: " + source)
    if changing_source == "markings":
        if first["marked_crosswalk_observed"] or not second["marked_crosswalk_observed"] or \
           not first["both_devices_operating_during_crossing"] or \
           not second["both_devices_operating_during_crossing"]:
            raise ValueError("marked crossing distinction absent")
    elif first["marked_crosswalk_observed"] or second["marked_crosswalk_observed"] or \
         not first["both_devices_operating_during_crossing"] or \
         second["both_devices_operating_during_crossing"]:
        raise ValueError("device operation distinction absent")
    return {"comparison_id": comparison_id, "case_ids": [first["case_id"], second["case_id"]],
            "sealed_attempts_compared": True, "legal_verdict": None,
            "physical_acceptance": False}
