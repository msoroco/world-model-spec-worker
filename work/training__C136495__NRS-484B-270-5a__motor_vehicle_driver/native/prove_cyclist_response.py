"""Positive and negative 600-frame source-shaped CPU proof."""

from cyclist_response import FRAME_COUNT, FRAME_RATE, measure_trace, response_command


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


identity = {
    "rider_actor_id": "rider-1", "bicycle_actor_id": "bicycle-1",
    "wheel_evidence": "synthetic fixture only", "propulsion_evidence": "synthetic fixture only",
    "moped_exclusion_evidence": "synthetic fixture only",
}
rows = []
for i in range(FRAME_COUNT):
    t = i / FRAME_RATE
    rows.append({
        "frame": i, "time_s": t,
        "ego_x_m": 8.0 * t, "ego_y_m": 0.0, "ego_vx_mps": 8.0, "ego_vy_mps": 0.0, "ego_radius_m": 1.0,
        "rider_x_m": 30.0 + 4.0 * t, "rider_y_m": 3.0, "rider_vx_mps": 4.0,
        "rider_vy_mps": 0.0, "rider_radius_m": 0.5,
        "bicycle_x_m": 30.0 + 4.0 * t, "bicycle_y_m": 3.0,
        "bicycle_vx_mps": 4.0, "bicycle_vy_mps": 0.0,
        "collision_sensor_contact": False,
    })

assert response_command("early_response", 20.0, 8.0)["brake"] > 0
assert response_command("later_response", 20.0, 8.0)["brake"] == 0
assert response_command("later_response", 10.0, 8.0)["brake"] > 0
reject(lambda: response_command("legal_violation", 20.0, 8.0), "unrecognized")
measured = measure_trace(rows, identity)
assert measured["frames"] == 600 and measured["duration_s"] == 30.0
assert measured["minimum_projected_ttc_s"] is not None
assert measured["legal_due_care_conclusion"] is None
assert measured["source_kind"] == "unverified_raw_actor_fields"
reject(lambda: measure_trace(rows[:-1], identity), "600 frames")
bad_identity = dict(identity)
bad_identity["wheel_evidence"] = ""
reject(lambda: measure_trace(rows, bad_identity), "physical identity")
bad_rows = [dict(row) for row in rows]
bad_rows[25]["time_s"] = 9.0
reject(lambda: measure_trace(bad_rows, identity), "20 Hz join")
bad_rows = [dict(row) for row in rows]
del bad_rows[25]["collision_sensor_contact"]
reject(lambda: measure_trace(bad_rows, identity), "collision sensor")
bad_rows = [dict(row) for row in rows]
bad_rows[25]["bicycle_y_m"] = 8.0
reject(lambda: measure_trace(bad_rows, identity), "not associated")
bad_rows = [dict(row) for row in rows]
bad_rows[25]["bicycle_vx_mps"] = 0.0
reject(lambda: measure_trace(bad_rows, identity), "not associated")
bad_rows = [dict(row) for row in rows]
for key in ("rider_x_m", "bicycle_x_m"):
    bad_rows[25][key] += 2.0
reject(lambda: measure_trace(bad_rows, identity), "pose motion differs")
print("PASS: 600-frame cyclist response and raw-trace measurement positive/negative CPU proof")
