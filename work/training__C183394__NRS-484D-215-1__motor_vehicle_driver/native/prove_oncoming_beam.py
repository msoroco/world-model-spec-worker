"""Positive and negative 600-frame diagnostic beam-distance CPU proof."""

from oncoming_beam import FRAME_COUNT, FRAME_RATE, FIVE_HUNDRED_FEET_M, measure_trace, requested_beam


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


scene = {
    "road_position": "adjacent_shoulder", "road_source": "synthetic diagnostic shoulder map",
    "lighting_trigger": "night_interval", "trigger_source": "synthetic diagnostic clock and sunset",
    "oncoming_driver_source": "synthetic diagnostic driver",
    "eye_region_source": "synthetic diagnostic camera plan",
}
rows = []
for i in range(FRAME_COUNT):
    t = i / FRAME_RATE
    distance = 300.0 - 10.0*t
    rows.append({
        "frame": i, "time_s": t,
        "ego_x_m": 5*t, "ego_y_m": 2.0, "ego_heading_x": 1.0, "ego_heading_y": 0.0,
        "oncoming_x_m": 300.0-5*t, "oncoming_y_m": 2.0,
        "oncoming_heading_x": -1.0, "oncoming_heading_y": 0.0,
        "requested_beam_state": requested_beam(distance),
        "observed_light_state_bits": 3 if requested_beam(distance) == "low_beam" else 5,
        "lamp_state_source": "synthetic_native_sample",
        "eye_region_pixels_retained": True,
    })
assert FIVE_HUNDRED_FEET_M == 152.4
assert requested_beam(152.4) == "low_beam"
assert requested_beam(160.0) == "low_beam"
assert requested_beam(160.001) == "high_beam"
reject(lambda: requested_beam(-1.0), "invalid measured")
m = measure_trace(rows, scene)
assert m["frames"] == 600 and m["duration_s"] == 30.0
assert m["within_500_feet_frames"] > 0
assert m["high_beam_request_within_500_feet_frames"] == 0
assert m["preentry_low_beam_request_frames"] > 0
assert m["glare_at_eyes_conclusion"] is None
reject(lambda: measure_trace(rows[:-1], scene), "600 frames")
bad = [dict(row) for row in rows]
bad[30]["time_s"] = 9.0
reject(lambda: measure_trace(bad, scene), "20 Hz join")
bad = [dict(row) for row in rows]
bad[30]["oncoming_heading_x"] = 1.0
reject(lambda: measure_trace(bad, scene), "opposed headings")
bad = [dict(row) for row in rows]
bad[30]["lamp_state_source"] = ""
reject(lambda: measure_trace(bad, scene), "headlamp request")
bad = [dict(row) for row in rows]
bad[30]["observed_light_state_bits"] = 3
reject(lambda: measure_trace(bad, scene), "lamp readback differs")
bad_scene = dict(scene, trigger_source="")
reject(lambda: measure_trace(rows, bad_scene), "lighting-trigger source")
print("PASS: 600-frame oncoming-beam distance and request positive/negative CPU proof")
