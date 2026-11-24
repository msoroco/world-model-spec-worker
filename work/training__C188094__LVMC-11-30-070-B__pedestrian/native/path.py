"""Paired pedestrian path requests for an at-grade crossing near an overpass."""

FRAMES = 600
RATE_HZ = 20
CROSSING_X_M = {"crosswalk": 0.0, "outside": 12.0}


def target(case, frame):
    if case not in CROSSING_X_M or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("Unknown pedestrian case or frame")
    y = -6.0 if frame < 100 else -6.0 + 12.0 * min(frame - 100, 240) / 240
    return {"x_m": CROSSING_X_M[case], "y_m": y,
            "target_speed_mps": 1.0 if 100 <= frame < 340 else 0.0,
            "requested_overpass_deck_use": False}


def compare_requested_paths():
    inside = [target("crosswalk", i) for i in range(FRAMES)]
    outside = [target("outside", i) for i in range(FRAMES)]
    if not all(a["y_m"] == b["y_m"] and a["target_speed_mps"] == b["target_speed_mps"]
               and a["requested_overpass_deck_use"] is False
               and b["requested_overpass_deck_use"] is False
               for a, b in zip(inside, outside)):
        raise ValueError("Non-crosswalk route policy changed")
    return {"frame_count": FRAMES, "rate_hz": RATE_HZ,
            "only_requested_difference": "at_grade_crossing_x_m",
            "physical_result": "unobserved"}
