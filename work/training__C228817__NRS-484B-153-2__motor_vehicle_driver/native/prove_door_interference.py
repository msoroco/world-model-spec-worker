"""Positive and negative 600-frame diagnostic door/traffic CPU proof."""

from door_interference import FRAME_COUNT, FRAME_RATE, door_request, measure_trace


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


scene = {
    "parked_vehicle_source": "synthetic diagnostic vehicle", "traffic_side_source": "synthetic diagnostic map",
    "passing_lane_source": "synthetic diagnostic lane", "door_hinge_source": "synthetic diagnostic door",
    "boarding_person_source": "synthetic diagnostic person", "door_side": "closest_to_passing_traffic",
}
rows = []
for i in range(FRAME_COUNT):
    t = i / FRAME_RATE
    rows.append({
        "frame": i, "time_s": t,
        "door_hinge_x_m": 0.0, "door_hinge_y_m": 0.0,
        "door_length_m": 1.0, "door_angle_rad": 0.8,
        "passing_x_m": -20.0+8*t, "passing_y_m": 2.0,
        "passing_radius_m": 0.8, "passing_vx_mps": 8.0, "passing_vy_mps": 0.0,
        "vehicle_stopped": True, "door_open": 200 <= i < 400,
        "person_boarding_or_alighting": 230 <= i < 250,
        "passing_vehicle_in_lane": True,
    })
assert door_request("earlier_open", 4.0)
assert not door_request("later_open", 4.0)
reject(lambda: door_request("legal_interference", 4.0), "unknown door")
m = measure_trace(rows, scene)
assert m["frames"] == 600 and m["duration_s"] == 30.0
assert m["door_open_frames"] == 200 and m["person_transfer_frames"] == 20
assert m["minimum_door_segment_to_vehicle_surface_gap_m"] is not None
assert m["legal_interference_conclusion"] is None
reject(lambda: measure_trace(rows[:-1], scene), "600 frames")
bad = [dict(row) for row in rows]
bad[30]["time_s"] = 10.0
reject(lambda: measure_trace(bad, scene), "20 Hz join")
bad = [dict(row) for row in rows]
bad[30]["door_open"] = None
reject(lambda: measure_trace(bad, scene), "door, person")
bad = [dict(row, passing_vx_mps=0.0) for row in rows]
reject(lambda: measure_trace(bad, scene), "moving vehicular traffic")
bad_scene = dict(scene, door_side="curb_side")
reject(lambda: measure_trace(rows, bad_scene), "traffic-side door")
print("PASS: 600-frame door-sweep and passing-traffic positive/negative CPU proof")
