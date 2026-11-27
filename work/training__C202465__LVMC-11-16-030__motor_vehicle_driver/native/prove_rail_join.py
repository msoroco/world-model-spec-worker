"""Prove original body/ray/device join rejects stale or missing sources."""

from rail_join import joined_row


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


frame = 12
body = {"frame": frame, "actor_id": 1, "actor_type_id": "vehicle.test",
        "body_vertices_m": [[x, 0, 0] for x in [-2, -2, -2, -2, 2, 2, 2, 2]],
        "velocity_mps": [6, 0, 0]}
direction = {"actor_id": 2, "rail_rays": [{"clear": True}],
             "body_rays": [{"clear": True}], "clear_distance_m": 121.92,
             "actor_position_m": [0, -70, 0],
             "rail_vehicle_visible_proxy": True}
rays = {"frame": frame, "ego_actor_id": 1, "review_source_sha256": "a"*64,
        "observer_m": [-1, 0, 1.4], "crossing": {"clear": True, "method": "cast_ray"},
        "directions": {"left": dict(direction), "right": dict(direction, actor_id=3,
                                                             actor_position_m=[0, 70, 0])}}
reviews = {"railway": {"source_sha256": "a"*64, "crossing_xyz_m": [0, 0, 0]},
           "approach": {"approach_direction_xy": [1, 0]}}
flagman = {"frame": frame, "source_ref": "original:flagman", "on_duty": False}
signal = {"frame": frame, "source_ref": "original:signal", "installed": True,
          "visible": True, "indicates_approach": False}
row = joined_row(frame, body, rays, reviews, flagman, signal)
assert row["traversing_grade_crossing"] is True
assert row["speed_mps"] == 6
assert row["crossing_signal_installed_visible"] and not row["signal_indicates_train_approach"]
reject(lambda: joined_row(frame, dict(body, frame=11), rays, reviews, flagman, signal), "frame join")
reject(lambda: joined_row(frame, body, dict(rays, review_source_sha256="b"*64), reviews, flagman, signal), "hash differs")
reject(lambda: joined_row(frame, body, dict(rays, directions={"left": direction}), reviews, flagman, signal), "both original")
reject(lambda: joined_row(frame, body, rays, reviews, dict(flagman, frame=11), signal), "flagman frame")
reject(lambda: joined_row(frame, body, rays, reviews, flagman, dict(signal, source_ref="")), "signal frame")
print("PASS: exact original frame, actor, ray, railway review and device joins")
