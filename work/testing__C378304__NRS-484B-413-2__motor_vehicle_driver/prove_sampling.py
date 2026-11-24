"""CPU diagnostic for saved 20 Hz right-turn signal threshold probes."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from signal_controller import request_right_signal
from signal_measure import compare, measure

ASSIGNMENT = "testing__C378304__NRS-484B-413-2__motor_vehicle_driver"
CASES = ("short80", "continuous100", "above101", "interrupted", "rain")


def prove() -> dict:
    scratch = Path(__file__).resolve().parents[2] / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    measured = {}
    with tempfile.TemporaryDirectory(prefix="c378304-sampling-", dir=scratch) as directory:
        for case in CASES:
            case_id = ASSIGNMENT + "__" + case
            rows = []
            for frame in range(101):
                remaining = max(0.0, 40.0 - frame * .4)
                rows.append({"frame": frame, "x_m": -remaining, "y_m": 0.0,
                             "right_signal": request_right_signal(case, remaining,
                                                                  speed_m_s=8.0),
                             "course_change": frame == 100})
            source = Path(directory) / (case + ".json")
            source.write_text(json.dumps({
                "format": "native-turn-signal-samples-v1", "case_id": case_id,
                "ego_actor": "motor_vehicle_driver", "context": {
                    "highway_source": "diagnostic-highway", "district_source": "diagnostic-business",
                    "frontage_source": "diagnostic-frontage", "building_use_source": "diagnostic-use",
                    "loading_zone_source": "diagnostic-loading-zone", "district_kind": "business",
                    "maneuver": "right_turn", "weather_source": "diagnostic-rain" if case == "rain" else "diagnostic-clear"},
                "samples": rows}, indent=2) + "\n")
            measured[case] = measure(source, case_id)
    assert measured["short80"]["continuous_distance_ft"] < 100
    assert measured["continuous100"]["continuous_distance_ft"] >= 100
    assert measured["above101"]["continuous_distance_ft"] > 101
    assert measured["interrupted"]["continuous_distance_ft"] < 100
    comparisons = {
        "business_right_distance": compare(measured["short80"], measured["continuous100"],
                                           "business_right_distance"),
        "signal_continuity": compare(measured["continuous100"], measured["interrupted"],
                                     "signal_continuity"),
        "regardless_weather": compare(measured["continuous100"], measured["rain"],
                                      "regardless_weather")}
    return {"format": "diagnostic-turn-signal-sampling-proof",
            "sample_rate_hz": 20, "speed_m_s": 8.0,
            "continuous_distances_ft": {case: measured[case]["continuous_distance_ft"] for case in CASES},
            "comparisons": comparisons, "physical_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), indent=2))
