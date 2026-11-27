"""Exact 20 Hz duration requests for controlled nighttime parking probes.

These are requested stop frames. Only original motion and clock sources can
establish a measured continuous parking episode.
"""

RATE_HZ = 20
TOTAL_FRAMES = 36063
TARGETS = {
    "below_30": 1799.0,
    "at_30": 1800.0,
    "above_30": 1801.0,
}


def stop_frame(case_id):
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in TARGETS:
        raise ValueError("Unknown exact duration case")
    return TOTAL_FRAMES - 1 - round(TARGETS[suffix] * RATE_HZ)


def request(case_id, frame):
    if not isinstance(frame, int) or frame < 0 or frame >= TOTAL_FRAMES:
        raise ValueError("Frame outside synchronized duration contract")
    stopping = stop_frame(case_id)
    return {"frame": frame,
            "phase": "approach" if frame < stopping else "parking_request",
            "target_speed_mps": 1.5 if frame < stopping else 0.0,
            "brake_request": frame >= stopping,
            "requested_stationary_duration_s": (TOTAL_FRAMES - 1 - stopping) / RATE_HZ,
            "physical_or_legal_acceptance": False}


def comparison_invariants(configs):
    if set(configs) != set(TARGETS):
        raise ValueError("Exact below/at/above duration triple required")
    fixed = ("law_id", "cell_id", "actor", "rate_hz", "capture_frames",
             "duration_s", "road_sha256", "prototype_blueprint", "cameras",
             "weather", "parking_target_xy_m", "source_context_policy")
    reference = configs["below_30"]
    for suffix, config in configs.items():
        if any(config.get(key) != reference.get(key) for key in fixed):
            raise ValueError("Duration comparison changed a held condition")
        if config.get("parking_stop_frame") != stop_frame(config["case_id"]):
            raise ValueError("Duration stop frame differs: " + suffix)
        if config.get("capture_frames") != TOTAL_FRAMES or config.get("rate_hz") != RATE_HZ:
            raise ValueError("Capture does not cover full threshold bracket")
    return {"passed": True, "held_fields": list(fixed),
            "duration_targets_s": TARGETS,
            "physical_or_legal_acceptance": False}
