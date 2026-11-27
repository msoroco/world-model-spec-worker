"""Positive and negative 600-frame rail-sight diagnostic CPU proof."""

from rail_sight import FRAME_COUNT, FRAME_RATE, FIFTEEN_MPH_MPS, measure_trace, speed_request


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


crossing = {
    "grade_crossing_source": "synthetic diagnostic crossing map",
    "railway_source": "synthetic diagnostic railway",
    "approach_route_source": "synthetic diagnostic route",
}
rows = []
for i in range(FRAME_COUNT):
    distance = 50.0 - 0.12*i
    rows.append({
        "frame": i, "time_s": i / FRAME_RATE,
        "distance_to_crossing_m": distance,
        "speed_mps": 6.0,
        "rail_left_clear_distance_m": 100.0,
        "rail_right_clear_distance_m": 130.0,
        "traversing_grade_crossing": -5.0 <= distance <= 0,
        "crossing_visible": True,
        "left_traffic_visible": False,
        "right_traffic_visible": True,
        "flagman_on_duty": False,
        "crossing_signal_installed_visible": False,
        "signal_indicates_train_approach": False,
        "observer_pose_source": f"synthetic_native_sample_pose_{i}",
        "observer_xy_m": [distance * -1, 0.0],
        "rail_ray_source": f"synthetic_native_sample_left_right_{i}",
    })
assert speed_request("slower_traversal") < FIFTEEN_MPH_MPS
assert speed_request("faster_traversal") > FIFTEEN_MPH_MPS
reject(lambda: speed_request("legal_violation"), "unknown traversal")
m = measure_trace(rows, crossing)
assert m["frames"] == 600 and m["duration_s"] == 30.0
assert m["last_100_feet_missing_view_frames"] > 0
assert m["legal_visibility_conclusion"] is None
reject(lambda: measure_trace(rows[:-1], crossing), "600 frames")
bad = [dict(row) for row in rows]
bad[200]["time_s"] = 99.0
reject(lambda: measure_trace(bad, crossing), "20 Hz join")
bad = [dict(row) for row in rows]
bad[200]["rail_ray_source"] = ""
reject(lambda: measure_trace(bad, crossing), "two-direction ray source")
bad = [dict(row, observer_xy_m=[-50.0, 0.0]) for row in rows]
reject(lambda: measure_trace(bad, crossing), "moving observer position")
bad_crossing = dict(crossing, railway_source="")
reject(lambda: measure_trace(rows, bad_crossing), "provenance required")
print("PASS: 600-frame rail-crossing sight and speed positive/negative CPU proof")
