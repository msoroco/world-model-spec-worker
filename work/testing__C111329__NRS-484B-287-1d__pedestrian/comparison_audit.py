"""Reject incomplete or confounded saved crossing comparisons."""

FIXED = ("map_sha256", "intersection_polygon", "walker_blueprint_id", "camera_contract_sha256", "duration_frames", "fps")


def audit(left: dict, right: dict, comparison: str) -> dict:
    if comparison not in {"diagonal_path_without_authority", "diagonal_device_authority", "authorized_device_path_control"}:
        raise ValueError("unknown comparison")
    for case in (left, right):
        for field in (*FIXED, "original_measurement", "device_inventory_sha256"):
            if field not in case or case[field] in (None, ""):
                raise ValueError(f"missing source-bound comparison field: {field}")
        if case["fps"] != 20 or case["duration_frames"] < 2:
            raise ValueError("capture contract mismatch")
        if not case["original_measurement"].get("walker_id") or not case["original_measurement"].get("device_source_hashes"):
            raise ValueError("original walker/device source missing")
    for field in FIXED:
        if left[field] != right[field]:
            raise ValueError(f"fixed condition differs: {field}")
    if comparison == "diagonal_device_authority":
        if left["route_kind"] != right["route_kind"] or left["route_kind"] != "opposite":
            raise ValueError("device comparison route changed")
        if left["authorization_observed"] == right["authorization_observed"]:
            raise ValueError("device authorization did not vary")
    else:
        if left["device_inventory_sha256"] != right["device_inventory_sha256"] or left["authorization_observed"] != right["authorization_observed"]:
            raise ValueError("route comparison device condition changed")
        if left["route_kind"] == right["route_kind"]:
            raise ValueError("route kind did not vary")
    return {"comparison_id": comparison, "passed": True, "case_ids": [left["case_id"], right["case_id"]]}
