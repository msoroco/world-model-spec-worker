"""Independent source-row comparisons for the two preparing indications."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver"
PAIRS = {
    "moving_vs_visible_movement": (BASE + "__selected_d6045110__condition_a",
                                   BASE + "__preparing_to_move__visible_vehicle_movement"),
    "movement_vs_hand_signal": (BASE + "__preparing_to_move__visible_vehicle_movement",
                                BASE + "__preparing_to_move__visible_driver_hand_signal"),
}
CONTEXT = ("officer_direction", "road_context_source_id", "weather_context_source_id",
           "posted_limit_mps", "visibility_m", "wet_road")
QUALIFICATION = ("kind", "flashing_state", "authorized_source_id",
                 "lamp_equipment_source_id", "lamp_qualification_source_id")


def rows(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines()]


def compare(pair, left_path, right_path):
    if pair not in PAIRS:
        raise ValueError("Unknown exact preparing comparison")
    left, right = rows(left_path), rows(right_path)
    if len(left) != 600 or len(right) != 600:
        raise ValueError("Comparison needs both 600-frame sources")
    expected = PAIRS[pair]
    if left[0].get("case_id") != expected[0] or right[0].get("case_id") != expected[1]:
        raise ValueError("Comparison case identities differ")
    if any(row.get("source_kind") != "synthetic_cpu_fixture"
           for row in left + right):
        raise ValueError("This diagnostic comparison requires explicit synthetic sources")
    for i, (a, b) in enumerate(zip(left, right)):
        if a.get("video_frame") != i or b.get("video_frame") != i or \
           a.get("native_frame") != b.get("native_frame") or \
           a.get("time_s") != b.get("time_s") or \
           a.get("camera_frames") != b.get("camera_frames"):
            raise ValueError("Comparison timeline/camera join differs at frame " + str(i))
        if any(a.get(key) != b.get(key) for key in CONTEXT):
            raise ValueError("Comparison fixed road/weather/officer context differs at frame " + str(i))
        av, bv = a["qualifying_vehicle"], b["qualifying_vehicle"]
        if any(av.get(key) != bv.get(key) for key in QUALIFICATION):
            raise ValueError("Comparison qualification differs at frame " + str(i))
        if a["ego"]["speed_mps"] != b["ego"]["speed_mps"]:
            raise ValueError("Comparison ego speed request differs at frame " + str(i))
    start_delta = round(left[0]["ego"]["road_x_m"] - right[0]["ego"]["road_x_m"], 5)
    vehicle_delta = round(left[0]["qualifying_vehicle"]["road_x_m"] -
                          right[0]["qualifying_vehicle"]["road_x_m"], 5)
    return {"format": "c405647-preparing-comparison-v1",
            "comparison_id": BASE + "__preparing__" + pair,
            "case_ids": list(expected),
            "source_sha256": [hashlib.sha256(Path(path).read_bytes()).hexdigest()
                              for path in (left_path, right_path)],
            "joined_frames": 600, "fixed_context_verified": True,
            "ego_start_delta_m": start_delta, "vehicle_start_delta_m": vehicle_delta,
            "fixed_geometry_verified": start_delta == 0 and vehicle_delta == 0,
            "controlled_comparison_claimed": start_delta == 0 and vehicle_delta == 0,
            "fixture_only": True, "physical_completion_claimed": False,
            "legal_outcome_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=PAIRS, required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.pair, args.left, args.right), indent=2, sort_keys=True))
