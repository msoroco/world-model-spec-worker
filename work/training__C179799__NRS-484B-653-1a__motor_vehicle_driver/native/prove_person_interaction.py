"""Positive and negative 600-frame diagnostic person-interaction CPU proof."""

from person_interaction import FRAME_COUNT, FRAME_RATE, control_request, measure_trace


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


scene = {
    "access_kind": "highway", "public_access_source": "synthetic diagnostic map",
    "driver_source": "synthetic diagnostic driver", "person_actor_source": "synthetic diagnostic person",
}
rows = []
for i in range(FRAME_COUNT):
    t = i / FRAME_RATE
    rows.append({
        "frame": i, "time_s": t,
        "ego_x_m": 8*t, "ego_y_m": 0.0, "ego_vx_mps": 8.0, "ego_vy_mps": 0.0,
        "ego_radius_m": 1.0, "ego_accel_longitudinal_mps2": 0.0,
        "ego_yaw_rate_radps": 0.0,
        "person_x_m": 25+2*t, "person_y_m": 2.0, "person_vx_mps": 2.0,
        "person_vy_mps": 0.0, "person_radius_m": 0.4,
        "collision_sensor_contact": False,
    })
assert control_request("earlier_response", 20.0)["brake"] > 0
assert control_request("later_response", 20.0)["brake"] == 0
reject(lambda: control_request("reckless", 20.0), "unknown interaction")
m = measure_trace(rows, scene)
assert m["frames"] == 600 and m["duration_s"] == 30.0
assert m["minimum_projected_ttc_s"] is not None
assert m["mental_state_conclusion"] is None and m["legal_recklessness_conclusion"] is None
reject(lambda: measure_trace(rows[:-1], scene), "600 frames")
bad = [dict(row) for row in rows]
bad[30]["time_s"] = 9.0
reject(lambda: measure_trace(bad, scene), "20 Hz join")
bad = [dict(row) for row in rows]
del bad[30]["ego_yaw_rate_radps"]
reject(lambda: measure_trace(bad, scene), "raw actor pose")
bad = [dict(row) for row in rows]
del bad[30]["collision_sensor_contact"]
reject(lambda: measure_trace(bad, scene), "collision sensor")
bad_scene = dict(scene, public_access_source="")
reject(lambda: measure_trace(rows, bad_scene), "public-access premises")
print("PASS: 600-frame person-interaction measurement positive/negative CPU proof")
