"""Unselected C104393 primary and three distinct Native candidate designs.

These are engineering inputs for executable bundles, not compatibility proof.
Triggers require original source measurements before any candidate may select.
"""
import json

FEET = (90, 100, 110, 290, 300, 310)
BASE = {
    "road_geometry": "hill_crest_left_curve_radius_20m",
    "controller_lookahead_m": 4.0,
    "camera_height_m": 3.5,
    "camera_fov_deg": 90,
    "duration_s": 42,
    "rate_hz": 20,
    "video_views": ("overview", "approach", "signal_close", "driver_reference"),
    "signal_policy": "continuous from assigned preturn station until turn exit",
    "other_vehicle_policy": "opposing lane; preserve the same path and timing across cases",
}
FALLBACKS = {
    "fallback1": {
        "changed": {"road_geometry": "hill_crest_left_curve_radius_24m"},
        "trigger": {"metric": "native_lane_link_and_body_containment",
                    "failure_condition": "Native route link absent or full body leaves the surveyed driving lane",
                    "required_source": "original Native map and body samples"},
    },
    "fallback2": {
        "changed": {"controller_lookahead_m": 3.0},
        "trigger": {"metric": "maximum_original_turn_route_error_m",
                    "failure_condition": "maximum error exceeds 0.35 m before turn exit",
                    "required_source": "original Native pose and route samples"},
    },
    "fallback3": {
        "changed": {"camera_height_m": 4.5, "camera_fov_deg": 105},
        "trigger": {"metric": "visible_signal_and_body_fraction",
                    "failure_condition": "source-video visibility is below 95% of approach frames",
                    "required_source": "original decoded camera pixels joined to Native frames"},
    },
}


def designs(feet):
    if feet not in FEET:
        raise ValueError("Unknown frozen C104393 planned case")
    common = dict(BASE, signal_start_ft=feet)
    result = {"primary": {"config": common, "trigger": None}}
    for name, entry in FALLBACKS.items():
        result[name] = {"config": dict(common, **entry["changed"]),
                        "changed_knobs": sorted(entry["changed"]),
                        "trigger": entry["trigger"]}
    return result


def check():
    all_cases = {}
    expected = {"primary", "fallback1", "fallback2", "fallback3"}
    metrics = {entry["trigger"]["metric"] for entry in FALLBACKS.values()}
    assert len(metrics) == 3
    for feet in FEET:
        case = designs(feet)
        assert set(case) == expected
        base = case["primary"]["config"]
        for name in FALLBACKS:
            candidate = case[name]
            changes = {key for key in base if base[key] != candidate["config"][key]}
            assert changes == set(candidate["changed_knobs"])
            assert candidate["trigger"]["required_source"].startswith("original ")
            assert candidate["config"]["signal_start_ft"] == feet
            assert candidate["config"]["duration_s"] == base["duration_s"]
            assert candidate["config"]["rate_hz"] == base["rate_hz"]
            assert candidate["config"]["video_views"] == base["video_views"]
            assert candidate["config"]["other_vehicle_policy"] == base["other_vehicle_policy"]
        all_cases[str(feet)] = case
    return {"format": "c104393-unselected-candidate-design-v1", "passed": True,
            "native_executed": False, "measured_trigger_crossings": False,
            "case_count": len(all_cases), "candidate_count": 4 * len(all_cases),
            "cases": all_cases}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
