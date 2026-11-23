"""Independent pair audit for bicycle encounter response comparisons."""


def audit_pair(brake, maintain):
    required = ("case_id", "map_sha256", "rider_kind", "rider_blueprint_id",
                "ego_route_sha256", "rider_route_sha256", "camera_plan_sha256",
                "duration_frames", "hz", "initial_ego_speed_mps", "initial_rider_speed_mps",
                "response", "observed_brake_peak", "original_history_sha256")
    for item in (brake, maintain):
        if any(key not in item or item[key] is None for key in required):
            raise ValueError("missing source-bound comparison evidence")
        if item["hz"] != 20 or item["duration_frames"] < 60:
            raise ValueError("comparison duration or sample rate unproved")
        if not item["original_history_sha256"] or len(item["original_history_sha256"]) != 64:
            raise ValueError("original history digest absent")
    for key in ("map_sha256", "rider_kind", "rider_blueprint_id", "ego_route_sha256",
                "rider_route_sha256", "camera_plan_sha256", "duration_frames", "hz"):
        if brake[key] != maintain[key]:
            raise ValueError("fixed comparison condition changed: " + key)
    for key in ("initial_ego_speed_mps", "initial_rider_speed_mps"):
        if abs(float(brake[key]) - float(maintain[key])) > 0.25:
            raise ValueError("initial speed condition changed: " + key)
    if brake["response"] != "brake" or maintain["response"] != "maintain":
        raise ValueError("response labels mismatched")
    if float(brake["observed_brake_peak"]) < 0.5 or float(maintain["observed_brake_peak"]) > 0.1:
        raise ValueError("declared response not observed")
    if brake["case_id"] == maintain["case_id"] or brake["original_history_sha256"] == maintain["original_history_sha256"]:
        raise ValueError("distinct source histories required")
    return {"comparison_complete": True, "rider_kind": brake["rider_kind"],
            "legal_judgment": "undetermined"}
